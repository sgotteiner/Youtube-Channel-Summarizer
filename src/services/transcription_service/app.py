import json
from pathlib import Path
import datetime
import asyncio
from src.pipeline.AudioTranscriber import AudioTranscriber
from src.utils.file_manager import FileManager
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video, VideoStatus
from src.utils.mongodb_client import mongodb_client
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer
from src.utils.async_helper import ServiceAsyncProcessor

logger = setup_logging()

# Global async processor instance to handle internal concurrency
service_processor = ServiceAsyncProcessor()

async def process_transcription_task_internal(video_id: str, session, queue_client: QueueClient, event_publisher: EventPublisher, kafka_producer: KafkaEventProducer):
    """
    Internal async method to handle a transcription task with full async capabilities.
    """
    video = session.query(Video).filter_by(id=video_id).first()
    if not video or not video.audio_file_path:
        logger.error(f"[{video_id}] Video record not found or audio_file_path is missing. Aborting transcription.")
        return

    logger.info(f"--- [Job: {video.job_id}] Starting audio transcription for video_id: {video_id} ---")

    video.status = VideoStatus.TRANSCRIBING
    session.commit()

    # Initialize the audio transcriber and call it
    audio_transcriber = AudioTranscriber(logger=logger)
    audio_path = Path(video.audio_file_path)

    # Call the transcription method (this involves API calls to Google, so it's I/O bound)
    # Pass the video_id to create unique chunk filenames and prevent race conditions
    transcription_text = await audio_transcriber.transcribe_audio(audio_path, video_id=video_id)

    # Save transcription even if empty - an empty transcription is still a valid result
    if transcription_text is not None:
        logger.info(f"[{video_id}] Transcription completed (length: {len(transcription_text or '')} characters).")

        # Save transcription to the shared filesystem for the summarization service to access
        file_manager = FileManager(channel_name=video.channel_name, is_openai_runtime=False, logger=logger)
        video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
        video_paths = file_manager.get_video_paths(video_data)
        transcription_path = video_paths["transcription"]
        
        # Create the directory if it doesn't exist and save the transcription to filesystem
        transcription_path.parent.mkdir(parents=True, exist_ok=True)
        import os
        os.makedirs(transcription_path.parent, exist_ok=True)
        with open(transcription_path, "w", encoding="utf-8") as f:
            f.write(transcription_text or "")
        logger.info(f"[{video_id}] Transcription saved to filesystem: {transcription_path}")

        video.status = VideoStatus.TRANSCRIBED
        
        # CRITICAL: Publish to next queue BEFORE committing to database to ensure pipeline continues even if DB updates fail
        try:
            queue_client.declare_queue('summarization_queue')
            logger.info(f"[{video_id}] Preparing to send message to summarization queue.")
            queue_client.publish_message('summarization_queue', { "video_id": video_id })
            logger.info(f"[{video_id}] SUCCESS: Message published to summarization queue.")
            session.commit()  # Only commit after queue message is successfully sent
            logger.info(f"[{video_id}] Database status updated to TRANSCRIBED in PostgreSQL.")
        except Exception as queue_error:
            logger.error(f"[{video_id}] FAILED to send message to summarization queue: {queue_error}")
            session.rollback()  # Rollback the status update
            return  # Exit the function, this will cause the video to not proceed in the pipeline

        # Publish events AFTER queue message is sent to ensure pipeline continues even if events fail
        try:
            event_payload = {
                "video_id": video_id, "job_id": video.job_id,
                "transcribed_at": datetime.datetime.utcnow().isoformat(),
                "character_count": len(transcription_text or '')
            }
            event_publisher.publish("TranscriptionCompleted", event_payload)
            logger.info(f"[{video_id}] SUCCESS: Event published to RabbitMQ exchange 'events_exchange'.")
            
            kafka_producer.send_event("transcription_completed", event_payload)
            logger.info(f"[{video_id}] SUCCESS: Event sent to Kafka topic 'transcription_completed'.")
        except Exception as event_error:
            logger.error(f"Error publishing events for video {video_id}, but transcription completed successfully: {event_error}")
    else:
        logger.error(f"[{video_id}] Failed to transcribe audio (method returned None).")
        video.status = VideoStatus.FAILED
        session.commit()


def process_transcription_task(channel, method, properties, body):
    """
    External callback from RabbitMQ - schedules the task for async processing.
    This allows multiple transcription tasks to run concurrently within the same service container.
    Message is acknowledged immediately to avoid delivery tag conflicts.
    """
    # Log that a message was received
    data = json.loads(body)
    video_id = data["video_id"]
    logger.info(f"[{video_id}] Received transcription task from RabbitMQ queue 'transcription_queue'.")
    
    # Acknowledge message immediately in the original thread to avoid delivery tag conflicts
    try:
        channel.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"[{video_id}] Message acknowledged in RabbitMQ consumer thread.")
    except Exception as e:
        logger.error(f"[{video_id}] Error acknowledging message immediately: {e}")
        return  # Exit early if we can't acknowledge

    async def handle_transcription_task():
        session = None
        event_publisher = None
        kafka_producer = None
        queue_client = None
        
        try:
            session = postgres_client.get_session()
            event_publisher = EventPublisher(logger=logger)
            kafka_producer = KafkaEventProducer(logger=logger)
            
            queue_client = QueueClient(logger=logger)
            
            await process_transcription_task_internal(video_id, session, queue_client, event_publisher, kafka_producer)
        except Exception as e:
            logger.error(f"Error during audio transcription for video {video_id}: {e}")
            if session:
                video = session.query(Video).filter_by(id=video_id).first()
                if video:
                    video.status = VideoStatus.FAILED
                    session.commit()
        finally:
            # Close connections gracefully, handling possible connection issues
            if session:
                try:
                    session.close()
                except Exception as e:
                    logger.warning(f"Failed to close database session: {e}")
            
            if event_publisher:
                try:
                    event_publisher.close()
                except Exception as e:
                    logger.warning(f"Failed to close event publisher: {e}")
            
            if kafka_producer:
                try:
                    kafka_producer.close()
                except Exception as e:
                    logger.warning(f"Failed to close Kafka producer: {e}")
                    
            if queue_client:
                try:
                    queue_client.close_connection()
                except Exception as e:
                    logger.warning(f"Failed to close queue client: {e}")

    # Schedule the task using the service processor helper (message already acknowledged)
    task = service_processor.schedule_task(handle_transcription_task())
    # Log that the task is scheduled
    logger.info(f"[{video_id}] Transcription task scheduled for async processing (task: {task}).")


def main():
    logger.info("Initializing Transcription Service Worker with async internal processing...")
    
    # Set up the service processor with the main event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    service_processor.set_loop(loop)
    
    def consume_messages():
        queue_client = QueueClient(logger=logger)
        queue_client.declare_queue('transcription_queue')
        queue_client.start_consuming('transcription_queue', process_transcription_task)

    # Run the queue consumer in a separate thread
    import threading
    consumer_thread = threading.Thread(target=consume_messages, daemon=True)
    consumer_thread.start()
    
    try:
        # Keep the main thread alive for async tasks
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Transcription Service shutting down...")
    finally:
        # Cancel all running tasks
        try:
            tasks = [task for task in asyncio.all_tasks(loop=loop) if not task.done()]
            for task in tasks:
                task.cancel()
            
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        except RuntimeError:
            # Event loop may be closed already
            pass
        finally:
            loop.close()
            logger.info("Transcription Service event loop closed.")

if __name__ == "__main__":
    main()
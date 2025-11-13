import json
from pathlib import Path
import datetime
import asyncio
from src.pipeline.AudioExtractor import AudioExtractor
from src.utils.file_manager import FileManager
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video, VideoStatus
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer
from src.utils.async_helper import ServiceAsyncProcessor

logger = setup_logging()

# Global async processor instance to handle internal concurrency
service_processor = ServiceAsyncProcessor()

async def process_audio_extraction_task_internal(video_id: str, session, queue_client: QueueClient, event_publisher: EventPublisher, kafka_producer: KafkaEventProducer):
    """
    Internal async method to handle an audio extraction task with full async capabilities.
    """
    video = session.query(Video).filter_by(id=video_id).first()
    if not video or not video.video_file_path:
        logger.error(f"[{video_id}] Video record not found or video_file_path is missing. Aborting audio extraction.")
        return

    logger.info(f"--- [Job: {video.job_id}] Starting audio extraction for video_id: {video_id} ---")

    # Initialize the audio extractor and file manager
    audio_extractor = AudioExtractor(logger=logger)
    file_manager = FileManager(channel_name=video.channel_name, is_openai_runtime=False, logger=logger)
    
    video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
    video_paths = file_manager.get_video_paths(video_data)
    audio_path = video_paths["audio"]

    # Call the extraction method (this is typically a file I/O operation)
    success = audio_extractor.extract_audio(Path(video.video_file_path), audio_path)

    if success:
        logger.info(f"[{video_id}] Audio extracted to: {audio_path}")
        video.status = VideoStatus.AUDIO_EXTRACTED
        video.audio_file_path = str(audio_path)
        
        # CRITICAL: Publish to next queue BEFORE committing to database to ensure pipeline continues even if DB updates fail
        try:
            queue_client.declare_queue('transcription_queue')
            logger.info(f"[{video_id}] Preparing to send message to transcription queue.")
            queue_client.publish_message('transcription_queue', { "video_id": video_id })
            logger.info(f"[{video_id}] SUCCESS: Message published to transcription queue.")
            session.commit()  # Only commit after queue message is successfully sent
            logger.info(f"[{video_id}] Database status updated to AUDIO_EXTRACTED in PostgreSQL.")
        except Exception as queue_error:
            logger.error(f"[{video_id}] FAILED to send message to transcription queue: {queue_error}")
            session.rollback()  # Rollback the status update
            return  # Exit the function, this will cause the video to not proceed in the pipeline

        # Publish events AFTER queue message is sent to ensure pipeline continues even if events fail
        try:
            event_payload = {
                "video_id": video_id, "job_id": video.job_id,
                "extracted_at": datetime.datetime.utcnow().isoformat(),
                "audio_file_path": str(audio_path)
            }
            event_publisher.publish("AudioExtracted", event_payload)
            logger.info(f"[{video_id}] SUCCESS: Event published to RabbitMQ exchange 'events_exchange'.")
            
            kafka_producer.send_event("audio_extracted", event_payload)
            logger.info(f"[{video_id}] SUCCESS: Event sent to Kafka topic 'audio_extracted'.")
        except Exception as event_error:
            logger.error(f"Error publishing events for video {video_id}, but audio extraction completed successfully: {event_error}")
    else:
        logger.error(f"[{video_id}] Failed to extract audio.")
        video.status = VideoStatus.FAILED
        session.commit()


def process_audio_extraction_task(channel, method, properties, body):
    """
    External callback from RabbitMQ - schedules the task for async processing.
    This allows multiple extraction tasks to run concurrently within the same service container.
    Message is acknowledged immediately to avoid delivery tag conflicts.
    """
    # Log that a message was received
    data = json.loads(body)
    video_id = data["video_id"]
    logger.info(f"[{video_id}] Received audio extraction task from RabbitMQ queue 'audio_extraction_queue'.")
    
    # Acknowledge message immediately in the original thread to avoid delivery tag conflicts
    try:
        channel.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"[{video_id}] Message acknowledged in RabbitMQ consumer thread.")
    except Exception as e:
        logger.error(f"[{video_id}] Error acknowledging message immediately: {e}")
        return  # Exit early if we can't acknowledge

    async def handle_extraction_task():
        session = None
        event_publisher = None
        kafka_producer = None
        queue_client = None
        
        try:
            session = postgres_client.get_session()
            event_publisher = EventPublisher(logger=logger)
            kafka_producer = KafkaEventProducer(logger=logger)
            
            queue_client = QueueClient(logger=logger)
            
            await process_audio_extraction_task_internal(video_id, session, queue_client, event_publisher, kafka_producer)
        except Exception as e:
            logger.error(f"Error during audio extraction for video {video_id}: {e}")
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
    task = service_processor.schedule_task(handle_extraction_task())
    # Log that the task is scheduled
    logger.info(f"[{video_id}] Audio extraction task scheduled for async processing (task: {task}).")


def main():
    logger.info("Initializing Audio Extraction Service Worker with async internal processing...")
    
    # Set up the service processor with the main event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    service_processor.set_loop(loop)
    
    def consume_messages():
        queue_client = QueueClient(logger=logger)
        queue_client.declare_queue('audio_extraction_queue')
        queue_client.start_consuming('audio_extraction_queue', process_audio_extraction_task)

    # Run the queue consumer in a separate thread
    import threading
    consumer_thread = threading.Thread(target=consume_messages, daemon=True)
    consumer_thread.start()
    
    try:
        # Keep the main thread alive for async tasks
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Audio Extraction Service shutting down...")
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
            logger.info("Audio Extraction Service event loop closed.")

if __name__ == "__main__":
    main()
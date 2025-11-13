import json
import time
import datetime
import asyncio
from src.pipeline.VideoDownloader import VideoDownloader
from src.utils.file_manager import FileManager
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video, VideoStatus
from src.utils.resilience import resilient_consumer
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer
from src.utils.async_helper import ServiceAsyncProcessor

logger = setup_logging()

# Global async processor instance to handle internal concurrency
service_processor = ServiceAsyncProcessor()

async def process_download_task_internal(video_id: str, session, queue_client: QueueClient, event_publisher: EventPublisher, kafka_producer: KafkaEventProducer):
    """
    Internal async method to handle a download task with full async capabilities.
    """
    video = session.query(Video).filter_by(id=video_id).first()
    if not video:
        logger.error(f"[{video_id}] Video not found in database. Aborting download.")
        return

    logger.info(f"--- [Job: {video.job_id}] Starting video download for video_id: {video_id} ---")
    
    video.status = VideoStatus.DOWNLOADING
    session.commit()

    # Initialize the downloader and file manager
    video_downloader = VideoDownloader(logger=logger)
    file_manager = FileManager(channel_name=video.channel_name, is_openai_runtime=False, logger=logger)
    
    video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
    video_paths = file_manager.get_video_paths(video_data)
    path_to_save_video = video_paths["video"].parent
    youtube_video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Call the download method (this is typically a sync operation, so it will block during file download)
    downloaded_path = video_downloader.download_video(
        youtube_video_url, video.title, video.upload_date, video.id, path_to_save_video
    )

    if downloaded_path:
        logger.info(f"[{video_id}] Downloaded to: {downloaded_path}")
        video.status = VideoStatus.DOWNLOADED
        video.video_file_path = str(downloaded_path)
        
        # CRITICAL: Publish to next queue BEFORE attempting event publishing that might fail
        # But AFTER updating status but before committing to database
        try:
            queue_client.declare_queue('audio_extraction_queue')
            logger.info(f"[{video_id}] Preparing to send message to audio extraction queue.")
            queue_client.publish_message('audio_extraction_queue', { "video_id": video_id })
            logger.info(f"[{video_id}] SUCCESS: Message published to audio extraction queue.")
            session.commit()  # Only commit after queue message is successfully sent
            logger.info(f"[{video_id}] Database status updated to DOWNLOADED in PostgreSQL.")
        except Exception as queue_error:
            logger.error(f"[{video_id}] FAILED to send message to audio extraction queue: {queue_error}")
            session.rollback()  # Rollback the status update
            return  # Exit the function, this will cause the video to not proceed in the pipeline

        # Publish events AFTER queue message is sent to ensure pipeline continues even if events fail
        try:
            event_payload = {
                "video_id": video_id, "job_id": video.job_id,
                "downloaded_at": datetime.datetime.utcnow().isoformat(),
                "file_path": str(downloaded_path)
            }
            event_publisher.publish("VideoDownloaded", event_payload)
            logger.info(f"[{video_id}] SUCCESS: Event published to RabbitMQ exchange 'events_exchange'.")
            
            kafka_producer.send_event("video_downloaded", event_payload)
            logger.info(f"[{video_id}] SUCCESS: Event sent to Kafka topic 'video_downloaded'.")
        except Exception as event_error:
            logger.error(f"Error publishing events for video {video_id}, but download completed successfully: {event_error}")
    else:
        logger.error(f"[{video_id}] Failed to download video (downloader returned None).")
        video.status = VideoStatus.FAILED
        session.commit()


def process_download_task_external(channel, method, properties, body):
    """
    External callback from RabbitMQ - schedules the task for async processing.
    This allows multiple download tasks to run concurrently within the same service container.
    Message is acknowledged immediately to avoid delivery tag conflicts.
    """
    # Log that a message was received
    data = json.loads(body)
    video_id = data["video_id"]
    logger.info(f"[{video_id}] Received download task from RabbitMQ queue 'download_queue'.")
    
    # Acknowledge message immediately in the original thread to avoid delivery tag conflicts
    try:
        channel.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"[{video_id}] Message acknowledged in RabbitMQ consumer thread.")
    except Exception as e:
        logger.error(f"[{video_id}] Error acknowledging message immediately: {e}")
        return  # Exit early if we can't acknowledge

    async def handle_download_task():
        session = None
        event_publisher = None
        kafka_producer = None
        queue_client = None
        
        try:
            session = postgres_client.get_session()
            event_publisher = EventPublisher(logger=logger)
            kafka_producer = KafkaEventProducer(logger=logger)
            
            queue_client = QueueClient(logger=logger)
            
            await process_download_task_internal(video_id, session, queue_client, event_publisher, kafka_producer)
        except Exception as e:
            logger.error(f"Error during video download for video {video_id}: {e}")
            if session:
                session.rollback()
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
    task = service_processor.schedule_task(handle_download_task())
    # Log that the task is scheduled
    logger.info(f"[{video_id}] Download task scheduled for async processing (task: {task}).")


@resilient_consumer(max_retries=3, delay=5)
def process_download_task(channel, method, properties, body):
    """
    Wrapper for the resilient consumer that schedules async tasks.
    """
    process_download_task_external(channel, method, properties, body)


def main():
    logger.info("Initializing Download Service Worker with async internal processing...")
    
    # Set up the service processor with the main event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    service_processor.set_loop(loop)
    
    def consume_messages():
        queue_client = QueueClient(logger=logger)
        queue_client.declare_queue('download_queue')
        queue_client.start_consuming('download_queue', process_download_task)

    # Run the queue consumer in a separate thread
    import threading
    consumer_thread = threading.Thread(target=consume_messages, daemon=True)
    consumer_thread.start()
    
    try:
        # Keep the main thread alive for async tasks
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Download Service shutting down...")
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
            logger.info("Download Service event loop closed.")

if __name__ == "__main__":
    main()

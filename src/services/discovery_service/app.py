import logging
import json
from typing import Dict, Optional
import datetime
import asyncio

from src.pipeline.VideoMetadataFetcher import VideoMetadataFetcher
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video, VideoStatus
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer
from src.utils.async_helper import ServiceAsyncProcessor

logger = setup_logging()

# Global async processor instance to handle internal concurrency
# Will be initialized with the event loop in main()
service_processor = ServiceAsyncProcessor()



def _is_video_valid(video_details: Dict, max_length: Optional[int], apply_max_length_for_captionless_only: bool, logger: logging.Logger) -> bool:
    duration = video_details.get("duration")
    if duration is None:
        logger.warning(f"Could not determine duration for '{video_details['video_title']}'. Skipping.")
        return False

    if max_length is None:
        return True

    is_too_long = (duration / 60.0) > float(max_length)

    if is_too_long:
        if apply_max_length_for_captionless_only and video_details["has_captions"]:
            logger.info(f"Video '{video_details['video_title']}' exceeds length limit, but has captions. It is valid.")
            return True
        
        logger.info(f"Skipping video '{video_details['video_title']}' (Length: {duration/60.0:.2f} min) as it exceeds the {max_length} min limit.")
        return False
    
    return True

async def process_discovery_task_internal(job_id: str, channel_name: str, num_videos_to_process: Optional[int], 
                                        max_video_length: Optional[int], apply_max_length_for_captionless_only: bool,
                                        queue_client: QueueClient, event_publisher: EventPublisher, kafka_producer: KafkaEventProducer):
    """
    Internal async method to handle a discovery task with full async capabilities.
    """
    logger.info(f"--- [Job: {job_id}] Starting video discovery for channel_name: {channel_name} ---")
    
    session = postgres_client.get_session()
    try:
        # Use the async helper by executing blocking operations in the thread pool
        metadata_fetcher = VideoMetadataFetcher(channel_name, logger=logger)

        # Get video entries (network I/O operation)
        video_entries = metadata_fetcher.get_video_entries()
        videos_to_process_count = 0
        
        for entry in video_entries:
            video_id = entry['id']
            
            existing_video = session.query(Video).filter_by(id=video_id).first()
            if existing_video:
                logger.info(f"[{video_id}] Video already exists in database with status '{existing_video.status}'. Skipping.")
                continue
            
            logger.info(f"[{video_id}] New video found. Fetching full video details...")
            # Fetch video details (network I/O operation) 
            video_details = metadata_fetcher.fetch_video_details(video_id)
            
            if not video_details:
                logger.warning(f"[{video_id}] Could not fetch video details. Skipping.")
                continue

            if _is_video_valid(video_details, max_video_length, apply_max_length_for_captionless_only, logger):
                logger.info(f"[{video_id}] Video is valid. Adding to database and publishing to download queue.")
                
                new_video = Video(
                    id=video_id, job_id=job_id, channel_name=channel_name,
                    title=video_details["video_title"], upload_date=video_details["upload_date"],
                    duration=video_details.get("duration"), status=VideoStatus.PENDING
                )
                session.add(new_video)
                
                # CRITICAL: Publish to next queue BEFORE committing to database to ensure pipeline continues even if DB updates fail
                # But AFTER adding to session but before committing so the video exists in DB when next service processes
                try:
                    logger.info(f"[{video_id}] Preparing to send message to download queue.")
                    queue_client.publish_message('download_queue', { "video_id": video_id })
                    logger.info(f"[{video_id}] SUCCESS: Message published to download queue.")
                    session.commit()  # Only commit after queue message is successfully sent
                    logger.info(f"[{video_id}] Video record added to database with status PENDING in PostgreSQL.")
                except Exception as queue_error:
                    logger.error(f"[{video_id}] FAILED to send message to download queue: {queue_error}")
                    session.rollback()  # Rollback the session to avoid partially committed state
                    continue  # Skip this video and continue with the next one

                # Publish events AFTER queue message is sent to ensure pipeline continues even if events fail
                try:
                    event_payload = {
                        "video_id": video_id, "job_id": job_id, "channel_name": channel_name,
                        "title": new_video.title, "discovered_at": datetime.datetime.utcnow().isoformat()
                    }
                    event_publisher.publish("VideoDiscovered", event_payload)
                    logger.info(f"[{video_id}] SUCCESS: Event published to RabbitMQ exchange 'events_exchange'.")
                    
                    kafka_producer.send_event("video_discovered", event_payload)
                    logger.info(f"[{video_id}] SUCCESS: Event sent to Kafka topic 'video_discovered'.")
                except Exception as event_error:
                    logger.error(f"Error publishing events for video {video_id}, but discovery completed successfully: {event_error}")

                videos_to_process_count += 1
            else:
                logger.info(f"[{video_id}] Video is invalid. Skipping.")

            if num_videos_to_process is not None and videos_to_process_count >= num_videos_to_process:
                logger.info(f"Reached the limit of {num_videos_to_process} new videos to process for job {job_id}.")
                break
        
        logger.info(f"--- [Job: {job_id}] Discovery for channel {channel_name} complete. Found {videos_to_process_count} new videos. ---")

    except Exception as e:
        logger.error(f"Error during video discovery for job {job_id}, channel {channel_name}: {e}")
        session.rollback()
    finally:
        session.close()


def process_discovery_task(channel, method, properties, body):
    """
    External callback from RabbitMQ - schedules the task for async processing.
    This allows multiple tasks to be processed concurrently within the same service container.
    Message is acknowledged immediately to avoid delivery tag conflicts.
    """
    # Log that a message was received
    data = json.loads(body)
    job_id = data["job_id"]
    channel_name = data["channel_name"]
    logger.info(f"[Job: {job_id}] Received discovery task from RabbitMQ queue 'discovery_queue' for channel: {channel_name}.")
    
    # Acknowledge message immediately in the original thread to avoid delivery tag conflicts
    try:
        channel.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"[Job: {job_id}] Discovery message acknowledged in RabbitMQ consumer thread.")
    except Exception as e:
        logger.error(f"[Job: {job_id}] Error acknowledging message immediately: {e}")
        return  # Exit early if we can't acknowledge

    num_videos_to_process = data.get("num_videos_to_process")
    max_video_length = data.get("max_video_length")
    apply_max_length_for_captionless_only = data.get("apply_max_length_for_captionless_only", False)

    async def handle_discovery_task():
        session = None
        event_publisher = None
        kafka_producer = None
        queue_client = None
        
        try:
            session = postgres_client.get_session()
            event_publisher = EventPublisher(logger=logger)
            kafka_producer = KafkaEventProducer(logger=logger)
            
            queue_client = QueueClient(logger=logger)
            queue_client.declare_queue('download_queue')
            
            await process_discovery_task_internal(job_id, channel_name, num_videos_to_process, 
                                                max_video_length, apply_max_length_for_captionless_only,
                                                queue_client, event_publisher, kafka_producer)
        except Exception as e:
            logger.error(f"Error processing discovery task: {e}")
            # Error is logged but message is already acknowledged
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
    task = service_processor.schedule_task(handle_discovery_task())
    # Log that the task is scheduled
    logger.info(f"[Job: {job_id}] Discovery task scheduled for async processing (task: {task}).")


def main():
    logger.info("Initializing Discovery Service Worker with persistent event loop...")
    
    # Set up the event loop and service processor
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    service_processor.set_loop(loop)
    
    def consume_messages():
        queue_client = QueueClient(logger=logger)
        queue_client.declare_queue('discovery_queue')
        queue_client.start_consuming('discovery_queue', process_discovery_task)

    # Run the queue consumer in a separate thread
    import threading
    consumer_thread = threading.Thread(target=consume_messages, daemon=True)
    consumer_thread.start()
    
    try:
        # Keep the main thread alive for async tasks
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Discovery Service shutting down...")
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
            logger.info("Discovery Service event loop closed.")

if __name__ == "__main__":
    main()
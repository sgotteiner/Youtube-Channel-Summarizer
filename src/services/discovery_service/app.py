import logging
import json
from typing import Dict, Optional
import datetime

from src.pipeline.VideoMetadataFetcher import VideoMetadataFetcher
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video, VideoStatus
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer

logger = setup_logging()

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

def process_discovery_task(channel, method, properties, body):
    data = json.loads(body)
    job_id = data["job_id"]
    channel_id = data["channel_id"]
    num_videos_to_process = data.get("num_videos_to_process")
    max_video_length = data.get("max_video_length")
    apply_max_length_for_captionless_only = data.get("apply_max_length_for_captionless_only", False)

    logger.info(f"--- [Job: {job_id}] Starting video discovery for channel_id: {channel_id} ---")
    
    session = postgres_client.get_session()
    event_publisher = EventPublisher(logger=logger)
    kafka_producer = KafkaEventProducer(logger=logger)
    try:
        metadata_fetcher = VideoMetadataFetcher(channel_id=channel_id, logger=logger)
        queue_client = QueueClient(logger=logger)
        queue_client.declare_queue('download_queue')

        video_entries = metadata_fetcher.get_video_entries()
        videos_to_process_count = 0
        
        for entry in video_entries:
            video_id = entry['id']
            
            existing_video = session.query(Video).filter_by(id=video_id).first()
            if existing_video:
                logger.info(f"[{video_id}] Video already exists in database with status '{existing_video.status}'. Skipping.")
                continue
            
            logger.info(f"[{video_id}] New video found. Fetching full video details...")
            video_details = metadata_fetcher.fetch_video_details(video_id)
            
            if not video_details:
                logger.warning(f"[{video_id}] Could not fetch video details. Skipping.")
                continue

            if _is_video_valid(video_details, max_video_length, apply_max_length_for_captionless_only, logger):
                logger.info(f"[{video_id}] Video is valid. Adding to database and publishing to download queue.")
                
                new_video = Video(
                    id=video_id, job_id=job_id, channel_id=channel_id,
                    title=video_details["video_title"], upload_date=video_details["upload_date"],
                    duration=video_details.get("duration"), status=VideoStatus.PENDING
                )
                session.add(new_video)
                session.commit()

                queue_client.publish_message('download_queue', { "video_id": video_id })
                
                event_payload = {
                    "video_id": video_id, "job_id": job_id, "channel_id": channel_id,
                    "title": new_video.title, "discovered_at": datetime.datetime.utcnow().isoformat()
                }
                event_publisher.publish("VideoDiscovered", event_payload)
                kafka_producer.send_event("video_discovered", event_payload)

                videos_to_process_count += 1
            else:
                logger.info(f"[{video_id}] Video is invalid. Skipping.")

            if num_videos_to_process is not None and videos_to_process_count >= num_videos_to_process:
                logger.info(f"Reached the limit of {num_videos_to_process} new videos to process for job {job_id}.")
                break
        
        queue_client.close_connection()
        logger.info(f"--- [Job: {job_id}] Discovery for channel {channel_id} complete. Found {videos_to_process_count} new videos. ---")

    except Exception as e:
        logger.error(f"Error during video discovery for job {job_id}, channel {channel_id}: {e}")
        session.rollback()
    finally:
        session.close()
        event_publisher.close()
        kafka_producer.close()
    
    channel.basic_ack(delivery_tag=method.delivery_tag)

def main():
    logger.info("Initializing Discovery Service Worker...")
    queue_client = QueueClient(logger=logger)
    queue_client.declare_queue('discovery_queue')
    queue_client.start_consuming('discovery_queue', process_discovery_task)

if __name__ == "__main__":
    main()
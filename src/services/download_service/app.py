import json
import time
import datetime
from src.pipeline.VideoDownloader import VideoDownloader
from src.utils.file_manager import FileManager
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video, VideoStatus
from src.utils.resilience import resilient_consumer
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer

logger = setup_logging()

@resilient_consumer(max_retries=3, delay=5)
def process_download_task(channel, method, properties, body):
    data = json.loads(body)
    video_id = data["video_id"]
    
    session = postgres_client.get_session()
    event_publisher = EventPublisher(logger=logger)
    kafka_producer = KafkaEventProducer(logger=logger)
    try:
        video = session.query(Video).filter_by(id=video_id).first()
        if not video:
            logger.error(f"[{video_id}] Video not found in database. Aborting download.")
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"--- [Job: {video.job_id}] Starting video download for video_id: {video_id} ---")
        
        video.status = VideoStatus.DOWNLOADING
        session.commit()

        video_downloader = VideoDownloader(logger=logger)
        file_manager = FileManager(channel_id=video.channel_id, is_openai_runtime=False, logger=logger)
        
        video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
        video_paths = file_manager.get_video_paths(video_data)
        path_to_save_video = video_paths["video"].parent
        youtube_video_url = f"https://www.youtube.com/watch?v={video_id}"

        downloaded_path = video_downloader.download_video(
            youtube_video_url, video.title, video.upload_date, video.id, path_to_save_video
        )

        if downloaded_path:
            logger.info(f"[{video_id}] Downloaded to: {downloaded_path}")
            video.status = VideoStatus.DOWNLOADED
            video.video_file_path = str(downloaded_path)
            session.commit()
            
            queue_client = QueueClient(logger=logger)
            queue_client.declare_queue('audio_extraction_queue')
            queue_client.publish_message('audio_extraction_queue', { "video_id": video_id })
            queue_client.close_connection()

            event_payload = {
                "video_id": video_id, "job_id": video.job_id,
                "downloaded_at": datetime.datetime.utcnow().isoformat(),
                "file_path": str(downloaded_path)
            }
            event_publisher.publish("VideoDownloaded", event_payload)
            kafka_producer.send_event("video_downloaded", event_payload)
        else:
            raise Exception("Failed to download video (downloader returned None).")

    except Exception as e:
        logger.error(f"Error during video download for job {video.job_id if 'video' in locals() and video else 'N/A'}, video {video_id}: {e}")
        if 'video' in locals() and video:
            video.status = VideoStatus.FAILED
            session.commit()
        raise e
    finally:
        session.close()
        event_publisher.close()
        kafka_producer.close()
        channel.basic_ack(delivery_tag=method.delivery_tag)

def main():
    logger.info("Initializing Download Service Worker...")
    queue_client = QueueClient(logger=logger)
    queue_client.declare_queue('download_queue')
    queue_client.start_consuming('download_queue', process_download_task)

if __name__ == "__main__":
    main()

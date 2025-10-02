import json
from pathlib import Path
import datetime
from src.pipeline.AudioExtractor import AudioExtractor
from src.utils.file_manager import FileManager
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video, VideoStatus
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer

logger = setup_logging()

def process_audio_extraction_task(channel, method, properties, body):
    data = json.loads(body)
    video_id = data["video_id"]

    session = postgres_client.get_session()
    event_publisher = EventPublisher(logger=logger)
    kafka_producer = KafkaEventProducer(logger=logger)
    try:
        video = session.query(Video).filter_by(id=video_id).first()
        if not video or not video.video_file_path:
            logger.error(f"[{video_id}] Video record not found or video_file_path is missing. Aborting audio extraction.")
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"--- [Job: {video.job_id}] Starting audio extraction for video_id: {video_id} ---")

        audio_extractor = AudioExtractor(logger=logger)
        file_manager = FileManager(channel_id=video.channel_id, is_openai_runtime=False, logger=logger)
        
        video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
        video_paths = file_manager.get_video_paths(video_data)
        audio_path = video_paths["audio"]

        success = audio_extractor.extract_audio(Path(video.video_file_path), audio_path)

        if success:
            logger.info(f"[{video_id}] Audio extracted to: {audio_path}")
            video.status = VideoStatus.AUDIO_EXTRACTED
            video.audio_file_path = str(audio_path)
            session.commit()
            
            queue_client = QueueClient(logger=logger)
            queue_client.declare_queue('transcription_queue')
            queue_client.publish_message('transcription_queue', { "video_id": video_id })
            queue_client.close_connection()

            event_payload = {
                "video_id": video_id, "job_id": video.job_id,
                "extracted_at": datetime.datetime.utcnow().isoformat(),
                "audio_file_path": str(audio_path)
            }
            event_publisher.publish("AudioExtracted", event_payload)
            kafka_producer.send_event("audio_extracted", event_payload)
        else:
            logger.error(f"[{video_id}] Failed to extract audio.")
            video.status = VideoStatus.FAILED
            session.commit()

    except Exception as e:
        logger.error(f"Error during audio extraction for job {video.job_id}, video {video_id}: {e}")
        video.status = VideoStatus.FAILED
        session.commit()
    finally:
        session.close()
        event_publisher.close()
        kafka_producer.close()

    channel.basic_ack(delivery_tag=method.delivery_tag)

def main():
    logger.info("Initializing Audio Extraction Service Worker...")
    queue_client = QueueClient(logger=logger)
    queue_client.declare_queue('audio_extraction_queue')
    queue_client.start_consuming('audio_extraction_queue', process_audio_extraction_task)

if __name__ == "__main__":
    main()
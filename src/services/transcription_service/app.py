import json
from pathlib import Path
import datetime
from src.pipeline.AudioTranscriber import AudioTranscriber
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video, VideoStatus
from src.utils.mongodb_client import mongodb_client
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer

logger = setup_logging()

def process_transcription_task(channel, method, properties, body):
    data = json.loads(body)
    video_id = data["video_id"]

    session = postgres_client.get_session()
    event_publisher = EventPublisher(logger=logger)
    kafka_producer = KafkaEventProducer(logger=logger)
    try:
        video = session.query(Video).filter_by(id=video_id).first()
        if not video or not video.audio_file_path:
            logger.error(f"[{video_id}] Video record not found or audio_file_path is missing. Aborting transcription.")
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"--- [Job: {video.job_id}] Starting audio transcription for video_id: {video_id} ---")

        video.status = VideoStatus.TRANSCRIBING
        session.commit()

        audio_transcriber = AudioTranscriber(logger=logger)
        transcription_text = audio_transcriber.transcribe_audio(Path(video.audio_file_path))

        if transcription_text:
            logger.info(f"[{video_id}] Transcription successful.")
            
            mongodb_client.transcriptions.update_one(
                {"video_id": video_id},
                {"$set": {"video_id": video_id, "transcription": transcription_text, "job_id": video.job_id}},
                upsert=True
            )
            logger.info(f"[{video_id}] Transcription saved to MongoDB.")

            video.status = VideoStatus.TRANSCRIBED
            session.commit()

            queue_client = QueueClient(logger=logger)
            queue_client.declare_queue('summarization_queue')
            queue_client.publish_message('summarization_queue', { "video_id": video_id })
            queue_client.close_connection()

            event_payload = {
                "video_id": video_id, "job_id": video.job_id,
                "transcribed_at": datetime.datetime.utcnow().isoformat(),
                "character_count": len(transcription_text)
            }
            event_publisher.publish("TranscriptionCompleted", event_payload)
            kafka_producer.send_event("transcription_completed", event_payload)
        else:
            logger.error(f"[{video_id}] Failed to transcribe audio (Whisper returned empty).")
            video.status = VideoStatus.FAILED
            session.commit()

    except Exception as e:
        logger.error(f"Error during audio transcription for job {video.job_id}, video {video_id}: {e}")
        video.status = VideoStatus.FAILED
        session.commit()
    finally:
        session.close()
        event_publisher.close()
        kafka_producer.close()

    channel.basic_ack(delivery_tag=method.delivery_tag)

def main():
    logger.info("Initializing Transcription Service Worker...")
    queue_client = QueueClient(logger=logger)
    queue_client.declare_queue('transcription_queue')
    queue_client.start_consuming('transcription_queue', process_transcription_task)

if __name__ == "__main__":
    main()
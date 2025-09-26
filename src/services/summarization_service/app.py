import json
import asyncio
import threading
import datetime
from flask import Flask, jsonify, request
from flasgger import Swagger
from ...pipeline.AgentSummarizer import OpenAISummarizerAgent
from ...utils.logger import setup_logging
from ...utils.queue_client import QueueClient
from ...utils.postgresql_client import postgres_client, Video, VideoStatus
from ...utils.mongodb_client import mongodb_client
from ...utils.event_publisher import EventPublisher
from ...utils.kafka_producer import KafkaEventProducer

logger = setup_logging()
app = Flask(__name__)
swagger = Swagger(app, template_file='../../documentation/summarization_api.yaml')

def process_summarization_task(channel, method, properties, body):
    data = json.loads(body)
    video_id = data["video_id"]

    session = postgres_client.get_session()
    event_publisher = EventPublisher(logger=logger)
    kafka_producer = KafkaEventProducer(logger=logger)
    try:
        video = session.query(Video).filter_by(id=video_id).first()
        if not video:
            logger.error(f"[{video_id}] Video record not found. Aborting summarization.")
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"--- [Job: {video.job_id}] Starting summarization for video_id: {video_id} ---")

        transcription_doc = mongodb_client.transcriptions.find_one({"video_id": video_id})
        if not transcription_doc or "transcription" not in transcription_doc:
            logger.error(f"[{video_id}] Transcription not found in MongoDB. Aborting.")
            video.status = VideoStatus.FAILED
            session.commit()
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        transcription_text = transcription_doc["transcription"]
        video.status = VideoStatus.SUMMARIZING
        session.commit()

        summarizer_agent = OpenAISummarizerAgent(is_openai_runtime=True, logger=logger)
        summary_text = asyncio.run(summarizer_agent.summary_call(transcription_text))

        if summary_text:
            mongodb_client.summaries.update_one(
                {"video_id": video_id},
                {"$set": {"video_id": video_id, "summary": summary_text, "job_id": video.job_id}},
                upsert=True
            )
            logger.info(f"[{video_id}] Summary saved to MongoDB.")
            video.status = VideoStatus.COMPLETED
            session.commit()
            logger.info(f"--- [Job: {video.job_id}] Successfully completed processing for video_id: {video_id} ---")

            event_payload = {
                "video_id": video_id, "job_id": video.job_id,
                "summarized_at": datetime.datetime.utcnow().isoformat(),
                "summary_length": len(summary_text)
            }
            event_publisher.publish("SummarizationCompleted", event_payload)
            kafka_producer.send_event("summarization_completed", event_payload)
        else:
            logger.error(f"[{video_id}] Failed to generate summary.")
            video.status = VideoStatus.FAILED
            session.commit()

    except Exception as e:
        logger.error(f"Error during summarization for job {video.job_id}, video {video_id}: {e}")
        video.status = VideoStatus.FAILED
        session.commit()
    finally:
        session.close()
        event_publisher.close()
        kafka_producer.close()

    channel.basic_ack(delivery_tag=method.delivery_tag)

def start_worker():
    logger.info("Initializing Summarization Service Worker...")
    queue_client = QueueClient(logger=logger)
    queue_client.declare_queue('summarization_queue')
    queue_client.start_consuming('summarization_queue', process_summarization_task)

@app.route("/summarize-text", methods=["POST"])
def summarize_text():
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "Missing text parameter"}), 400

    text_to_summarize = data["text"]
    logger.info("Received request for stateless summarization.")

    try:
        summarizer_agent = OpenAISummarizerAgent(is_openai_runtime=True, logger=logger)
        summary_text = asyncio.run(summarizer_agent.summary_call(text_to_summarize))

        if summary_text:
            return jsonify({"summary": summary_text}), 200
        else:
            logger.error("Stateless summarization failed to generate summary.")
            return jsonify({"error": "Failed to generate summary"}), 500
    except Exception as e:
        logger.error(f"Error during stateless summarization: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    worker_thread = threading.Thread(target=start_worker, daemon=True)
    worker_thread.start()
    app.run(debug=True, port=5005)

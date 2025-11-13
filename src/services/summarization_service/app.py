import json
import asyncio
import threading
import datetime
from flask import Flask, jsonify, request
from flasgger import Swagger
from src.pipeline.AgentSummarizer import OpenAISummarizerAgent
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video, VideoStatus
from src.utils.mongodb_client import mongodb_client
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer
from src.utils.async_helper import ServiceAsyncProcessor
from src.utils.file_manager import FileManager
import aiofiles

logger = setup_logging()

# Global async processor instance to handle internal concurrency
service_processor = ServiceAsyncProcessor()

app = Flask(__name__)
swagger = Swagger(app, template_file='/app/apis/summarization_api.yaml')

async def process_summarization_task_internal(video_id: str, session, queue_client: QueueClient, event_publisher: EventPublisher, kafka_producer: KafkaEventProducer):
    """
    Internal async method to handle a summarization task with full async capabilities.
    """
    video = session.query(Video).filter_by(id=video_id).first()
    if not video:
        logger.error(f"[{video_id}] Video record not found. Aborting summarization.")
        return

    logger.info(f"--- [Job: {video.job_id}] Starting summarization for video_id: {video_id} ---")

    # Instead of looking in MongoDB, read the transcription from the filesystem
    file_manager = FileManager(channel_name=video.channel_name, is_openai_runtime=False, logger=logger)
    video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
    video_paths = file_manager.get_video_paths(video_data)
    transcription_path = video_paths["transcription"]
    
    if not transcription_path.exists():
        logger.error(f"[{video_id}] Transcription file not found at {transcription_path}. Aborting.")
        video.status = VideoStatus.FAILED
        session.commit()
        return

    try:
        async with aiofiles.open(transcription_path, "r", encoding="utf-8") as f:
            transcription_text = await f.read()
    except Exception as e:
        logger.error(f"[{video_id}] Error reading transcription file: {e}. Aborting.")
        video.status = VideoStatus.FAILED
        session.commit()
        return
    video.status = VideoStatus.SUMMARIZING
    session.commit()

    # Use the restored recursive summarization functionality with async
    summarizer_agent = OpenAISummarizerAgent(is_openai_runtime=True, logger=logger)
    summary_text = await summarizer_agent.summary_call(transcription_text)

    if summary_text:
        logger.info(f"[{video_id}] Preparing to save summary to MongoDB.")
        
        # Update MongoDB summary
        result = mongodb_client.summaries.update_one(
            {"video_id": video_id},
            {"$set": {"video_id": video_id, "summary": summary_text, "job_id": video.job_id}},
            upsert=True
        )
        
        # Update the video status in database
        video.status = VideoStatus.COMPLETED
        
        # CRITICAL: We don't publish to any downstream queue since summarization is the final step
        # So we just commit the database update
        session.commit()
        
        logger.info(f"[{video_id}] SUCCESS: Summary saved to MongoDB with upsert result: {result.upserted_id is not None or result.modified_count > 0}.")
        logger.info(f"[{video_id}] Database status updated to COMPLETED in PostgreSQL.")
        logger.info(f"--- [Job: {video.job_id}] Successfully completed processing for video_id: {video_id} ---")

        # Publish events after the main processing is complete but before connection cleanup
        try:
            event_payload = {
                "video_id": video_id, "job_id": video.job_id,
                "summarized_at": datetime.datetime.utcnow().isoformat(),
                "summary_length": len(summary_text)
            }
            event_publisher.publish("SummarizationCompleted", event_payload)
            logger.info(f"[{video_id}] SUCCESS: Event published to RabbitMQ exchange 'events_exchange'.")
            
            kafka_producer.send_event("summarization_completed", event_payload)
            logger.info(f"[{video_id}] SUCCESS: Event sent to Kafka topic 'summarization_completed'.")
        except Exception as event_error:
            logger.error(f"Error publishing events for video {video_id}, but summarization completed successfully: {event_error}")
    else:
        logger.error(f"[{video_id}] Failed to generate summary.")
        video.status = VideoStatus.FAILED
        session.commit()


def process_summarization_task(channel, method, properties, body):
    """
    Direct async processing of summarization tasks.
    This allows multiple summarization tasks to run concurrently within the same service container.
    Message is acknowledged immediately to avoid delivery tag conflicts.
    """
    # Log that a message was received
    data = json.loads(body)
    video_id = data["video_id"]
    logger.info(f"[{video_id}] Received summarization task from RabbitMQ queue 'summarization_queue'.")
    
    # Acknowledge message immediately in the original thread to avoid delivery tag conflicts
    try:
        channel.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"[{video_id}] Message acknowledged in RabbitMQ consumer thread.")
    except Exception as e:
        logger.error(f"[{video_id}] Error acknowledging message immediately: {e}")
        return  # Exit early if we can't acknowledge

    async def handle_summarization_task():
        session = None
        event_publisher = None
        kafka_producer = None
        queue_client = None
        
        try:
            session = postgres_client.get_session()
            event_publisher = EventPublisher(logger=logger)
            kafka_producer = KafkaEventProducer(logger=logger)
            
            queue_client = QueueClient(logger=logger)
            
            await process_summarization_task_internal(video_id, session, queue_client, event_publisher, kafka_producer)
        except Exception as e:
            logger.error(f"Error during summarization for video {video_id}: {e}")
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
    task = service_processor.schedule_task(handle_summarization_task())
    # Log that the task is scheduled
    logger.info(f"[{video_id}] Summarization task scheduled for async processing (task: {task}).")


def start_worker():
    logger.info("Initializing Summarization Service Worker with async internal processing...")
    
    # Set up the service processor with the main event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    service_processor.set_loop(loop)
    
    def consume_messages():
        queue_client = QueueClient(logger=logger)
        queue_client.declare_queue('summarization_queue')
        queue_client.start_consuming('summarization_queue', process_summarization_task)

    # Run the queue consumer in a separate thread
    consumer_thread = threading.Thread(target=consume_messages, daemon=True)
    consumer_thread.start()
    
    try:
        # Keep the main thread alive for async tasks
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Summarization Service shutting down...")
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
            logger.info("Summarization Service event loop closed.")

@app.route("/summarize-text", methods=["POST"])
def summarize_text():
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "Missing text parameter"}), 400

    text_to_summarize = data["text"]
    logger.info("Received request for stateless summarization.")

    try:
        # Use the restored async summarization functionality
        summarizer_agent = OpenAISummarizerAgent(is_openai_runtime=True, logger=logger)
        
        # Create and run the async function in a new event loop
        async def get_summary():
            return await summarizer_agent.summary_call(text_to_summarize)
        
        summary_text = asyncio.run(get_summary())

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
    app.run(debug=True, host='0.0.0.0', port=5005)

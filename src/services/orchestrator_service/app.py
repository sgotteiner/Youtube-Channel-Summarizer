import logging
import uuid
from flask import Flask, jsonify, request
from flasgger import Swagger
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient
from src.utils.postgresql_client import postgres_client, Video

app = Flask(__name__)
logger = setup_logging()
swagger = Swagger(app, template_file='/app/apis/orchestrator_api.yaml')

@app.route("/jobs", methods=["POST"])
def create_job():
    """
    Endpoint to create a new summarization job.
    ---
    (This docstring is now handled by the template_file)
    """
    data = request.get_json()
    if not data or not data.get("channel_id"):
        return jsonify({"error": "Missing channel_id parameter"}), 400

    channel_id = data.get("channel_id")
    job_id = str(uuid.uuid4())
    logger.info(f"Received new job request for channel_id: {channel_id}. Assigned job_id: {job_id}")

    try:
        queue_client = QueueClient(logger=logger)
        queue_client.declare_queue('discovery_queue')
        
        message = {
            "job_id": job_id,
            "channel_id": channel_id,
            "num_videos_to_process": data.get("num_videos_to_process", 5),
            "max_video_length": data.get("max_video_length", 30),
            "apply_max_length_for_captionless_only": data.get("apply_max_length_for_captionless_only", True)
        }
        
        queue_client.publish_message('discovery_queue', message)
        queue_client.close_connection()

        return jsonify({"job_id": job_id, "message": "Job accepted and queued for processing."}), 202

    except Exception as e:
        logger.error(f"An unexpected error occurred during job creation for job {job_id}: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route("/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """
    Endpoint to get the status of a job.
    ---
    (This docstring is now handled by the template_file)
    """
    logger.info(f"Fetching status for job_id: {job_id}")
    session = postgres_client.get_session()
    try:
        videos = session.query(Video).filter(Video.job_id == job_id).all()
        if not videos:
            return jsonify({"error": "Job not found"}), 404
        
        video_statuses = [
            {
                "video_id": v.id,
                "title": v.title,
                "status": v.status.name if v.status else "UNKNOWN",
                "upload_date": v.upload_date
            } for v in videos
        ]
        return jsonify({"job_id": job_id, "videos": video_statuses}), 200
    except Exception as e:
        logger.error(f"Error fetching status for job {job_id}: {e}")
        return jsonify({"error": "Failed to retrieve job status"}), 500
    finally:
        session.close()

if __name__ == "__main__":
    app.run(debug=True, port=5000)

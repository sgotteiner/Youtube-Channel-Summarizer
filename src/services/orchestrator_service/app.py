"""
Orchestrator Service - Provides API endpoints to start jobs and check status.
"""
import uuid
from flask import Flask, jsonify, request
from flasgger import Swagger
from src.utils.logger import setup_logging
from src.utils.queue_manager import QueueManager
from src.utils.db_manager import DatabaseManager


class OrchestratorService:
    def __init__(self):
        self.logger = setup_logging()
        self.app = Flask(__name__)
        self.swagger = Swagger(self.app, template_file='/app/apis/orchestrator_api.yaml')
        self.queue_manager = QueueManager(self.logger)
        self.db_manager = DatabaseManager(self.logger)
        self._setup_routes()

    def _setup_routes(self):
        """Setup API routes."""
        @self.app.route("/jobs", methods=["POST"])
        def create_job():
            """
            Endpoint to create a new summarization job.
            """
            data = request.get_json()
            if not data or not data.get("channel_name"):
                return jsonify({"error": "Missing channel_name parameter"}), 400

            channel_name = data.get("channel_name")
            job_id = str(uuid.uuid4())
            self.logger.info("Received new job request for channel_name: %s. Assigned job_id: %s", channel_name, job_id)

            try:
                message = {
                    "job_id": job_id,
                    "channel_name": channel_name,
                    "num_videos_to_process": data.get("num_videos_to_process", 5),
                    "max_video_length": data.get("max_video_length", 30),
                    "apply_max_length_for_captionless_only": data.get("apply_max_length_for_captionless_only", True)
                }

                if not self.queue_manager.send_message('discovery_queue', message):
                    return jsonify({"error": "Failed to queue job"}), 500

                return jsonify({"job_id": job_id, "message": "Job accepted and queued for processing."}), 202

            except Exception as e:
                self.logger.error("An unexpected error occurred during job creation for job %s: %s", job_id, e)
                return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

        @self.app.route("/jobs/<job_id>", methods=["GET"])
        def get_job_status(job_id):
            """
            Endpoint to get the status of a job.
            """
            self.logger.info("Fetching status for job_id: %s", job_id)
            try:
                videos = self.db_manager.get_videos_by_job(job_id)
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
                self.logger.error("Error fetching status for job %s: %s", job_id, e)
                return jsonify({"error": "Failed to retrieve job status"}), 500

    def run(self, debug=True, host='0.0.0.0', port=5000):
        """Run the Flask app."""
        self.app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":
    service = OrchestratorService()
    service.run()
"""
Transcription Service - Transcribes audio files using the service framework.
"""
from src.pipeline.AudioTranscriber import AudioTranscriber
from src.patterns.ServiceTemplatePattern import ServiceTemplate


class TranscriptionService(ServiceTemplate[str]):
    def __init__(self):
        from src.enums.service_enums import ServiceType
        super().__init__(ServiceType.TRANSCRIPTION)
        self.audio_transcriber = AudioTranscriber(self.logger)

    def get_input_file_path(self, video_paths):
        """
        Transcription service needs the audio file as input.
        """
        return video_paths["audio"]  # Input is the audio file

    async def perform_specific_operation(self, video, input_file_path, video_paths, video_id: str) -> str:
        # Transcription service needs the input audio file path and outputs to transcription path
        audio_path = input_file_path
        transcription_path = video_paths["transcription"]

        # Transcribe and save the audio using the pipeline tool (automatically logs status)
        result_path = await self.audio_transcriber.transcribe_audio_and_save(
            audio_path, transcription_path, video_id=video_id
        )

        return str(result_path) if result_path else None

    def get_service_specific_event_fields(self, video_id: str, video, result: str) -> dict:
        return {
            "character_count": len(result) if result else 0
        }


if __name__ == "__main__":
    # Create and run the service
    service = TranscriptionService()
    service.run()
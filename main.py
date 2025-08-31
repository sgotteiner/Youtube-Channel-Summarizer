"""
Main module for the YouTube Channel Summarizer application.
"""

from pathlib import Path
from ChannelVideoDownloader import ChannelVideosDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor
from AgentSummarizer import OpenAISummarizerAgent


def main():
    """Main function to orchestrate the YouTube channel summarization process."""
    channel_name = 'TradeIQ'
    path_to_save_videos = f'./channel_videos/{channel_name}'
    path_to_save_transcriptions = f'./channel_transcriptions/{channel_name}'
    path_to_save_summaries = f'./channel_summaries/{channel_name}'
    
    # Create directories if they don't exist
    Path(path_to_save_videos).mkdir(parents=True, exist_ok=True)
    Path(path_to_save_transcriptions).mkdir(parents=True, exist_ok=True)
    Path(path_to_save_summaries).mkdir(parents=True, exist_ok=True)

    # Step 1: Download channel videos
    ChannelVideosDownloader(channel_name, path_to_save_videos, 2)
    exit()  # Early exit for testing

    # Step 2: Extract audio from videos
    video_name = "Artificial Intelligence Moving Average 100 Highly Profitable Trading Strategies"
    video_path = f'{path_to_save_videos}/{video_name}.mp4'
    # AudioExtractor(video_path)  # Extract audio from video

    # Step 3: Read transcription
    transcription_path = f"{path_to_save_transcriptions}/{video_name}.txt"
    with open(transcription_path, "r", encoding="utf-8") as file:
        transcription = file.read()

    # Step 4: Generate summary
    is_runtime = True
    summarizer = OpenAISummarizerAgent(is_runtime)
    summary = summarizer.summary_call(transcription)
    
    print("Transcription length:", len(transcription), "Summary length:", len(summary))
    
    # Step 5: Save summary
    summary_path = f'{path_to_save_summaries}/{video_name}.txt'
    with open(summary_path, "w") as file:
        file.write(summary)
    exit()  # Early exit for testing

    # Alternative: Transcribe audio directly
    audio_path = f'./channel_audios/{channel_name}/{video_name}.wav'
    audio_transcription = AudioTranscriber(audio_path).transcription
    print(audio_transcription)
    
    with open(transcription_path, "w") as file:
        file.write(audio_transcription)


if __name__ == '__main__':
    main()
from pathlib import Path

from ChannelVideoDownloader import ChannelVideosDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor
from AgentSummarizer import OpenAISummarizerAgent


def main():
    channel_name = 'TradeIQ'
    path_to_save_videos = f'./channel_videos/{channel_name}'
    path_to_save_transcriptions = f'./channel_transcriptions/{channel_name}'
    path_to_save_summaries = f'./channel_summaries/{channel_name}'
    Path(path_to_save_videos).mkdir(parents=True, exist_ok=True)
    Path(path_to_save_transcriptions).mkdir(parents=True, exist_ok=True)
    Path(path_to_save_summaries).mkdir(parents=True, exist_ok=True)

    ChannelVideosDownloader(channel_name, path_to_save_videos, 2)
    exit()

    video_name = "Artificial Intelligence Moving Average 100 Highly Profitable Trading Strategies"
    video_path = f'{path_to_save_videos}/{video_name}.mp4'
    audio_path = f'./channel_audios/{channel_name}/{video_name}.wav'
    # AudioExtractor(video_path)

    with open(f"{path_to_save_transcriptions}/{video_name}.txt", "r", encoding="utf-8") as file:
        transcription = file.read()
    is_runtime = True
    summarizer = OpenAISummarizerAgent(is_runtime)
    summary = summarizer.summary_call(transcription)
    print("transcription length:", len(transcription), "summary length:", len(summary))
    with open(f'{path_to_save_summaries}/{video_name}.txt', "w") as file:
        file.write(summary)
    exit()

    audio_transcription = AudioTranscriber(audio_path).transcription
    print(audio_transcription)
    with open(f'{path_to_save_transcriptions}/{video_name}.txt', "w") as file:
        file.write(audio_transcription)


if __name__ == '__main__':
    main()
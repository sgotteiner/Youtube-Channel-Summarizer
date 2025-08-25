from pathlib import Path

from ChannelVideoDownloader import ChannelVideosDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor


def main():
    channel_name = 'TradeIQ'
    path_to_save_videos = f'./channel_videos/{channel_name}'
    path_to_save_transcriptions = f'./channel_transcriptions/{channel_name}'
    Path(path_to_save_videos).mkdir(parents=True, exist_ok=True)
    Path(path_to_save_transcriptions).mkdir(parents=True, exist_ok=True)

    # ChannelVideosDownloader(channel_name, path_to_save_videos)

    video_name = "Artificial Intelligence Moving Average 100 Highly Profitable Trading Strategies"
    video_path = f'{path_to_save_videos}/{video_name}.mp4'
    audio_path = f'./channel_audios/{channel_name}/{video_name}.wav'
    # AudioExtractor(video_path)

    audio_transcription = AudioTranscriber(audio_path).transcription
    print(audio_transcription)
    with open(f'{path_to_save_transcriptions}/{video_name}.txt', "w") as file:
        file.write(audio_transcription)


if __name__ == '__main__':
    main()
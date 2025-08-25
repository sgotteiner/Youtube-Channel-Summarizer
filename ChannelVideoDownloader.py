from pytube import YouTube
import requests
import re


class ImageDownloader:
    def __init__(self, youtube_video_url, path_to_save_video):
        self.youtube_video_url = youtube_video_url
        self.path_to_save = path_to_save_video  # Path to save the downloaded video
        self.download_video()

    def download_video(self):
        try:
            yt = YouTube(self.youtube_video_url)
            video = yt.streams.filter(file_extension='mp4', progressive=True).first()
            video.download(self.path_to_save)
            print(f'Download successful. Video saved at: {self.path_to_save}')
        except Exception as e:
            print(f'Error: {e}')


class ChannelVideosDownloader:
    def __init__(self, channel_name, path_to_save_videos):
        """
        This class finds the videos of a YouTube channel by its name and downloads them. It only downloads the first 30
        because that's what javascript loads before dynamically loading more when scrolling down. Getting all the videos
        is possible using the YouTube API. It is probably also possible using web scraping.

        :param channel_name: The most convenient way to use the URL. sometimes it works better with the channel ID.
        This code works using the channel name but in order to use channel ID the url is 'https://www.youtube.com/channel<channel ID>
        The channel ID can be found at the page source of the channel page searching for "channel_id=".
        """

        self.channel_url = 'https://www.youtube.com/@' + channel_name

        self.video_urls = self.get_video_urls(self.channel_url)

        for url in self.video_urls:
            print(url)
            ImageDownloader(url, path_to_save_videos)

    def get_video_urls(self, channel_url):
        video_urls = []

        # Construct the URL for the channel's videos tab
        videos_url = f'{channel_url}/videos'

        # Send an HTTP GET request to the videos tab
        response = requests.get(videos_url)

        if response.status_code == 200:
            video_urls = re.findall(r'/watch\?v=[\w-]+', response.text)
            video_urls = ['https://www.youtube.com' + url for url in video_urls]

        return video_urls
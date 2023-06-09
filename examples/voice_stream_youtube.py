"""Stream audio from a specific YouTube video into a voice channel in the Discord."""
import asyncio
import re

from typing import Any

import discord
import youtube_dl
from discord import Intents

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(executor=None, func=lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class VoiceJoinerClient(discord.Client):
    def __init__(self, *, intents: Intents, **options: Any):
        super().__init__(intents=intents, **options)
        self.voice_channels = []
        self.joined_channel = None
        self.voice_client = None
        self.txt_channel = None

    # Overrides discord.Client.on_ready - an event that can be listened for.
    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        self.retrieve_voice_channels()

        for guild in self.guilds:
            for index, channel in enumerate(guild.text_channels):
                self.txt_channel = channel
                break

        await self.join_voice_channel(self.select_joining_channel())

    # Helper Methods
    def retrieve_voice_channels(self):
        """Retrieves all Voice channels in the guild that are visible
        to the bot and stores them in the class.

        :return:
        """

        for guild in self.guilds:
            for index, channel in enumerate(guild.voice_channels):
                self.voice_channels.append(channel)

    def display_channels(self):
        """Displays the directory of Voice channels the bot can see in the server."""

        print("\n[Voice Channels] :")
        for index, channel in enumerate(self.voice_channels):
            print(f"\t- [{index + 1}] `{channel}`")

    def select_joining_channel(self):
        """ Selects a Voice Channel in the Server to join.

        :return: discord.VoiceChannel - The Voice Channel the user selects.
        """

        self.display_channels()

        choice_index = None
        while choice_index is None:
            choice_index = input("Join Channel No. > ")
            try:
                choice_index = (int(choice_index) - 1)
            except ValueError:
                print("Please select a No.")
                choice_index = None

            if choice_index < 0 or choice_index > (len(self.voice_channels) - 1):
                print("Please select a Voice Channel No.")
                choice_index = None

        return self.voice_channels[choice_index]

    async def join_voice_channel(self, joining_channel):
        """Commands the bot to join a Voice Channel, emitting a sound
         when it does so.

        Will also update object state, assigning the discord.VoiceClient object,
        created during the connection process, to the `bot_in_voice_channel` field for future reference.

        :param joining_channel: The discord.VoiceChannel to have the bot connect to.
        """

        self.voice_client = await discord.VoiceChannel.connect(joining_channel)
        await self.stream_youtube()

    async def stream_youtube(self):
        """Stream the audio of a YouTube video in the joined channel.

        Notes: This was a while ago, and I need to verify if it's
        still the case, but there was a fatal bug with the latest
        version of youtube-dl via pip install youtube-dl. It was
        fixed in their GitHub, but not yet pushed to the package?
        TODO: Read up on this and verify.

            Pip install latest version (with fixes):
                pip install git+https://github.com/ytdl-org/youtube-dl.git@master#egg=youtube_dl

        """

        while True:  # I wish was a do-while loop
            url = input("YouTube Video > ")
            if youtube_url_match(url):
                break
            print("URL format appears to be incorrect.\nPlease enter a valid YouTube Video URL.")

        async with self.txt_channel.typing():
            player = await YTDLSource.from_url(url=url, loop=self.voice_client.loop, stream=True)
            self.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)


def youtube_url_match(url: str) -> bool:
    """Regex pattern matching a string to check if it contains
    the video id section that all YouTube video links appear to end with
    i.e `v=...`.

    This would be the video id sent to the YouTube API.

    :param url: str containing the URL to verify
    :return: true if the URL could be a YouTube video link
    """

    pattern = re.compile("(v=[_0-9A-Za-z]{11})")
    return re.search(pattern, url) is not None


def run(token):
    # Suppress noise about console usage from errors
    youtube_dl.utils.bug_reports_message = lambda: ''

    intents = discord.Intents.default()
    intents.message_content = True

    client = VoiceJoinerClient(intents=intents)
    client.run(token)

from streamlink.stream.stream import Stream, StreamIO
from streamlink import Streamlink
from .main import m3u8_link
from dataclasses import dataclass
from enum import StrEnum

class connection_states(StrEnum):
    disconnected = "disconnected"
    warm = "warm"
    streaming = "streaming"
class Stream_manager:
    def __init__(self,m3u8_link: m3u8_link):
        self.m3u8_link = m3u8_link

        self.stream_fd: dict[str,StreamIO] = {}
        self.cached_streams: dict[str,str] | None = None

        self.m3u8_url = m3u8_url = m3u8_link.url
        self.hls_url = m3u8_url if m3u8_url.startswith("hls://") else f"hls://{m3u8_url}"
        self.initiate_session()

    def initiate_connection_state(self):
        self.connection_mode = "disconnected"
    def initiate_session(self):
        session = self.session = Streamlink()
        session.set_option("hls-playlist-reload-attempts",5)
        session.set_option("http-headers", {
            "User-Agent": self.m3u8_link.user_agent,
            "Referer": self.m3u8_link.referer
        })
    
    def update_cached_streams(self):
        self.cached_streams = self.session.streams(self.hls_url)

    def open_stream(self,quality: str):
        self.stream_fd[quality] = self.cached_streams[quality].open()

    def close_stream(self,quality: str):

        if quality in self.stream_fd:
            http_timeout = self.session.get_option("http-timeout")
            stream_timeout = self.session.get_option("stream-timeout")
            self.session.set_option("http-timeout", 0.1)
            self.session.set_option("stream-timeout", 0.1)
            self.stream_fd[quality].close()
            self.session.set_option("http-timeout", http_timeout)
            self.session.set_option("stream-timeout", stream_timeout)
        else:
            print(f"'{quality}' not in open stream set. Skipping...")

    def close_all_streams(self):
        for stream_qualtiy in self.stream_fd:           
            self.close_stream(stream_qualtiy)


    def get_stream_chunk(self,quality: str,bytes: int = 64 * 1024):
        return self.stream_fd[quality].read(bytes)
    
    def stream(self):
        if not self.cached_streams:
            self.update_cached_streams()
        self.open_stream("best")
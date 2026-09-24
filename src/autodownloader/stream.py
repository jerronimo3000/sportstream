from streamlink.stream.stream import Stream, StreamIO
from streamlink import Streamlink
from .main import m3u8_link
from dataclasses import dataclass
from enum import StrEnum
import threading
import time

class connection_states(StrEnum):
    disconnected = "disconnected"
    warm = "warm"
    streaming = "streaming"
class Stream_manager:
    def __init__(self,m3u8_link: m3u8_link):
        self.initialize_m3u8_variables(m3u8_link)
        self.initialize_stream_variables()
        self.initialize_session()
        self.initialize_threading()
    def initialize_m3u8_variables(self,m3u8_link: m3u8_link):
        self.m3u8_url = m3u8_url = m3u8_link.url
        self.hls_url = m3u8_url if m3u8_url.startswith("hls://") else f"hls://{m3u8_url}"
        self.m3u8_link = m3u8_link
    def initialize_stream_variables(self):
        self.stream_fd: dict[str,StreamIO] = {}
        self.cached_streams: dict[str,str] | None = None
        self.streaming = False
    def initialize_session(self):
        session = self.session = Streamlink()
        session.set_option("hls-playlist-reload-attempts",5)
        session.set_option("http-headers", {
            "User-Agent": self.m3u8_link.user_agent,
            "Referer": self.m3u8_link.referer
        })
    def initialize_threading(self):
        self.lock = threading.Lock()
        self.warmer_thread = warmer_thread = threading.Thread(target=self.warm_stream, daemon=True)
        warmer_thread.start()
    def stop_threading(self):
        if self.warmer_thread and self.warmer_thread.is_alive():
            self.warmer_thread.join(timeout=2)

    def update_cached_streams(self):
        streams = self.session.streams(self.hls_url)
        with self.lock:
            self.cached_streams = streams
    def warm_stream(self):
        while True:
            with self.lock:
                if self.streaming:
                    break
            self.update_cached_streams()
            time.sleep(5)

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
        yield from self._stream()

    def _stream(self):
        self.streaming = True
        self.open_stream("best")
        try:
            while True:
                data = self.get_stream_chunk("best")
                if not data:
                    print("Stream has ended")
                    break
                yield data
        finally:
            print("closing stream")
            self.close_all_streams()
            self.streaming = False



class Stream_coordinator:
    def __init__(self):
        self.stream_managers: dict[str, Stream_manager] = {}

    def add_stream_manager(self,stream_manager: Stream_manager, game_id: str):
        self.stream_managers[game_id] = stream_manager

    def stream(self,game_id: str):
        yield from self.stream_managers[game_id].stream()


    
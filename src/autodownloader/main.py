import re
from playwright.sync_api import sync_playwright,Page,Browser,Request
from dataclasses import dataclass
import subprocess
import time
import requests
import streamlink
from streamlink import Streamlink
from streamlink.stream.hls import MuxedHLSStream
from pathlib import Path
from flask import Flask, Response, request,send_file,stream_with_context
from streamlink.stream.stream import Stream
from .plugins import Site_plugin,Development,Sportsurge, Dudestream, Nbabite, Streameast,Sportusa,Crackstreams,Playlist_request
import os
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from functools import cached_property
import json
from zoneinfo import ZoneInfo
from .constants import Constants
from enum import StrEnum
import threading
import queue
import logging
app = Flask(__name__)
from urllib.parse import urljoin
from typing import ClassVar
import traceback
from typing import ClassVar
import shutil
from .game_data import *

#logging.basicConfig(level=logging.DEBUG)
#logger=logging.getLogger("streamlink")
#logger.setLevel(logging.DEBUG)



def attempt_function(function: callable,arguments: dict = {},num_retries: int = 10,sleep_time: int = 0):
        attempts = 1
        while attempts <= num_retries:
            try:
                function_return = function(**arguments)
                return function_return
            except Exception as e:
                print(f"Error: {e} \nAttempt {attempts} of {num_retries} failed. Retrying...")
                attempts += 1
                if attempts > num_retries:
                    raise RuntimeError("Maximum number of retries reached")
                else:
                    time.sleep(sleep_time)


class Stream_manager:
    def __init__(self,stream_id: str,game_page_url: str, m3u8_link: Playlist_request = None):
        self.stream_id = stream_id
        self.game_page_url = game_page_url
        self.initialize_m3u8_variables(m3u8_link)
        self.initialize_stream_variables()
        self.initialize_session()
        self.initialize_threading()
        self.initialize_stream_repackager()

    def initialize_stream_repackager(self):
        if Playlist_request is None:
            self.get_m3u8_link()
        self.stream_repackager = Stream_repackager(self.stream_id,playlist_request=self.m3u8_link)
        
    def initialize_m3u8_variables(self,m3u8_link: Playlist_request):
        if m3u8_link is None:
            self.get_m3u8_link()
        self.update_hls_url()
    def initialize_stream_variables(self):
        self.stream_fd: dict[str,StreamIO] = {}
        self.cached_streams: dict[str,str] | None = None
        self.streaming = False
    def initialize_session(self):
        session = self.session = Streamlink()
        session.set_option("hls-live-restart",True)
        session.set_option("hls-playlist-reload-attempts",5)
        session.set_option("http-headers",self.m3u8_link.all_headers)
        
    def initialize_threading(self):
        self.lock = threading.Lock()
        self.warmer_thread = warmer_thread = threading.Thread(target=self.warm_stream, daemon=True)
        warmer_thread.start()
    def stop_threading(self):
        if self.warmer_thread and self.warmer_thread.is_alive():
            self.warmer_thread.join(timeout=2)
    def get_m3u8_link(self):
        self.m3u8_link = get_playlist_request(self.game_page_url)
    def update_hls_url(self):
        m3u8_url = self.m3u8_link.url
        self.hls_url = m3u8_url if m3u8_url.startswith("hls://") else f"hls://{m3u8_url}"

    def update_cached_streams(self):
        streams = self.session.streams(self.hls_url)
        with self.lock:
            self.cached_streams = streams
    def warm_stream(self):
        while True:
            with self.lock:
                if self.streaming:
                    break
            try:
                self.update_cached_streams()
                time.sleep(5)
            except Exception as e:
                print(e)
                self.get_m3u8_link()
                self.update_hls_url()

    def open_stream(self,quality: str):
        self.stream_fd[quality] = self.cached_streams[quality].open()

    def close_stream(self,quality: str):
        if quality in self.stream_fd:
            http_timeout = self.session.get_option("http-timeout")
            stream_timeout = self.session.get_option("stream-timeout")
            self.session.set_option("http-timeout", 5)
            self.session.set_option("stream-timeout", 5)
            self.stream_fd[quality].close()
            self.session.set_option("http-timeout", http_timeout)
            self.session.set_option("stream-timeout", stream_timeout)
        else:
            print(f"'{quality}' not in open stream set. Skipping...")

    def close_all_streams(self):
        for stream_qualtiy in self.stream_fd:           
            self.close_stream(stream_qualtiy)
        self.streaming = False
        print("All streams closed")

    def get_stream_chunk(self,quality: str,bytes: int = 64 * 1024):
        return self.stream_fd[quality].read(bytes)
    
    def stream(self):
        self.streaming = True
        if not self.cached_streams:
            self.update_cached_streams()
        attempts = 1
        while attempts <= 3 and self.streaming:
            try:
                yield from self._stream()
            except Exception as e:
                print(e)
                print(f"Attempting to update m3u8 url ({attempts} of {3})")
                attempts += 1
                self.get_m3u8_link()
                self.update_hls_url()
                self.update_cached_streams()

    def _stream(self):
        self.open_stream("best")
        while True:
            data = self.get_stream_chunk("best")
            if not data:
                print("Stream has ended")
                self.streaming = False
                break
            yield data

    def get_playlist(self):
        self.wait_for_cached_stream_initilization()
        stream = self.cached_streams["best"]
        if isinstance(stream,MuxedHLSStream):
            playlist_url = self.get_url_from_muxxed(stream)
        else:
            print(stream.args)
            playlist_url = stream.url
        playlist_contents = requests.get(playlist_url,headers=self.m3u8_link.all_headers)
        playlist_contents.raise_for_status()
        playlist_conditioned = self.replace_relative_with_full_url(playlist_url,playlist_contents.text)
        return playlist_conditioned
    
    def get_url_from_muxxed(self,stream: MuxedHLSStream) -> str:
        video_stream,audio_stream = stream.substreams
        url = video_stream.url
        return url
    
    def replace_relative_with_full_url(self,base_url: str,playlist: str):
        output = []
        for line in playlist.splitlines():
            if not self.is_url_line(line) or not self.is_relative_url(line):
                output.append(line)
            elif self.is_relative_url(line):
                output.append(urljoin(base_url,line.strip()))
            else:
                pass
        return "\n".join(output) + "\n"   

    def is_url_line(self,line: str) -> bool:
        return (not line.startswith("#")) and bool(line.split())

    def is_relative_url(self,line: str) -> bool:
        return not line.startswith("http")

    def wait_for_cached_stream_initilization(self):
        while not self.cached_streams:
            pass





class Stream_coordinator:
    def __init__(self):
        self.streams: dict[str, Site_plugin] = {}
        self.threads: dict[int,threading.Thread] = {}
        self.lock = threading.Lock()
    def add_stream(self,stream_id: str, stream: Site_plugin):
        with self.lock:
            if not stream_id in self.streams:
                self.streams[stream_id] = stream


def no_game_m3u_playlist():
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:10",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXTINF:10.0,",
        "http://192.168.50.109:8900/unavailable.ts"
    ]
    return "\n".join(lines)
    
def waiting_for_stream_playlist(stream_id: str) -> str:
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:10",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXTINF:10.0,",
        f"http://192.168.50.109:8900/waiting/{stream_id}"
    ]
    return "\n".join(lines)


COORDINATOR = Stream_coordinator()

@app.get("/<string:sport>/<int:channel_index>")
def restream(sport: str, channel_index: int):
    if request.method == "HEAD":
        return Response(status=200, mimetype="application/vnd.apple.mpegurl")

    #return send_seed_video()

    try:
        game_data_manager = Game_data_manager(sport,channel_index)
        print("Getting active game...")
        game = game_data_manager.nearest_game
        print(f"{game.team_1} are playing {game.team_2} at {game.time_start}")
        active_team = game.team_1
        print(game.id)
               
        if not game.id in COORDINATOR.streams:
            print(f"Adding game to coordinator ({game.id})")
            stream = Crackstreams(game)
            COORDINATOR.add_stream(game.id,stream)
        

        return Response(
            COORDINATOR.streams[game.id].get_playlist_local(),
            mimetype="application/vnd.apple.mpegurl"
        )

    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exception(e)
        return Response("Not Found", status=503)

def send_seed_video() -> Response:
    return Response(
            no_game_m3u_playlist(),
            mimetype="application/vnd.apple.mpegurl"
        )


@app.get("/playlist/<string:stream_id>/segments/<string:segment_id>.ts")
def serve_segment(stream_id: str, segment_id: str):
    return COORDINATOR.streams[stream_id].stream_repackager.serve_segment(segment_id)


        
def read_file_chunks(path):
    with open(path, "rb") as f:
        while chunk := f.read(188*100):
            yield chunk

def send_no_stream_available():
    for chunk in read_file_chunks("slate.ts"):
        yield chunk

@app.get("/unavailable.ts")
def no_stream_available():
    return Response(
        send_no_stream_available(),
        headers={"Content-Type": "video/mp2t"}
    )

def waiting_for_stream(stream_id: str):
    while COORDINATOR.stream_managers[stream_id].cached_streams is None:
        for chunk in read_file_chunks("slate.ts"):
            if COORDINATOR.stream_managers[stream_id].cached_streams is not None:
                break
            yield chunk

@app.get("/waiting/<string:stream_id>")
def waiting(stream_id: str):
    return Response(
        waiting_for_stream(stream_id),
        headers={"Content-Type": "video/mp2t"}
    )


@app.get("/development")
def development():
    if request.method == "HEAD":
        return Response(status=200, mimetype="application/vnd.apple.mpegurl")
    if not "dev" in COORDINATOR.streams:
        COORDINATOR.add_stream("development",
            Development("https://www.earthcam.com/usa/florida/lauderdalebythesea/town/?cam=lbts_beach")
            #Development("https://crackstreams.mx/stream/new-york-knicks-vs-indiana-pacers")
        #COORDINATOR.add_stream_manager(Stream_manager("dev","https://tvsportslive.fr/69371-2/"))
        )
    local_playlist = COORDINATOR.streams["development"].get_playlist_local()
    return Response(
        local_playlist,
        mimetype="application/vnd.apple.mpegurl"
    )

@app.get("/segments/<string:stream_id>/<string:segment>.ts")
def stream_segment(stream_id:str, segment:str):
    print(f"Incoming Range: {request.headers.get('Range')}")
    print(f"Fetching segment {segment}")
    original_segment_url = COORDINATOR.get_original_segment_url(stream_id,segment)
    print(f"Original segment:\n{original_segment_url}")
    headers = COORDINATOR.stream_managers[stream_id].m3u8_link.all_headers
    range_header = request.headers.get("Range")   # what ffmpeg asked for
    headers = dict(headers)                       # copy the stored headers
    if range_header:
        headers["Range"] = range_header          

    response = requests.get(
        original_segment_url,
        headers = headers,
        stream=True
    )
    print(f"Range sent to CDN: {headers.get('Range')}")
    print(f"CDN status: {response.status_code}")
    response.raise_for_status()
    print(f"Recieved segment ({response.elapsed})")

 # pass it on to the CDN

    content_type = response.headers.get("Content-Type", "video/mp2t")
    if content_type.startswith("image/"):
        content_type = "video/mp2t"
    out_headers = {"Content-Type": content_type}
    for name in ("Content-Range", "Accept-Ranges"):
        if name in response.headers:
            out_headers[name] = response.headers[name]


    return Response(
        stream_with_context(response.iter_content(chunk_size=64 * 1024)),
        status=response.status_code,
        headers=out_headers
        )
    
    






@app.route("/development.xml",methods=["GET"])
def get_development_epg():
    EPG_FILE_PATH = Path(__file__).resolve().parent / "data/development.xml"
    if not os.path.exists(EPG_FILE_PATH):
        return Response("<tv></tv>", mimetype="application/xml"), 404

    return send_file(EPG_FILE_PATH, mimetype="application/xml")

@app.route("/development.m3u", methods=["GET"])
def get_development_channels_m3u():
    m3u_path = Path(__file__).resolve().parent / "data/development.m3u"
    if not os.path.exists(m3u_path):
        return Response("#EXTM3U\n", mimetype="audio/x-mpegurl"), 404
    return send_file(m3u_path, mimetype="audio/x-mpegurl")
  
def is_recording_request(user_agent: str) -> bool:
    return "JELLYFIN-SERVER" in user_agent.upper()


@app.route("/epg.xml", methods=["GET"])
def get_epg():
    EPG_FILE_PATH = Path(__file__).resolve().parent / "data/epg.xml"
    if not os.path.exists(EPG_FILE_PATH):
        return Response("<tv></tv>", mimetype="application/xml"), 404

    return send_file(EPG_FILE_PATH, mimetype="application/xml")

@app.route("/m3u/<string:m3u_file>", methods=["GET"])
def get_channels_m3u(m3u_file: str):
    m3u_path = Path(__file__).resolve().parent / f"data/{m3u_file}"
    if not os.path.exists(m3u_path):
        return Response("#EXTM3U\n", mimetype="audio/x-mpegurl"), 404
    return send_file(m3u_path, mimetype="audio/x-mpegurl")


class Recording_writer:
    def __init__(self,game: Game):
        self.game = game

    @cached_property
    def sport_data(self):
        return get_sport_data()

    def recording_end_filepath(self) -> str:
        season = self.get_season()
        game_month= convert_to_str_with_leading_zeroes(datetime.fromisoformat(self.game.time_start).month,2)
        game_day = convert_to_str_with_leading_zeroes(datetime.fromisoformat(self.game.time_start).day,2)
        return f"{self.game.league} {self.game.sport}/Season {season}/{self.game.league} {self.game.sport} - S{season}E{game_month}{game_day} - {self.game.team_1} @ {self.game.team_2}.ts"


    def get_season(self):
        game_month = datetime.fromisoformat(self.game.time_start).month
        game_year = datetime.fromisoformat(self.game.time_start).year

        if self.season_crosses_years and game_month < self.league_month_end:
            season = game_year - 1
        else:
            season = game_year
        return season
        
    
    @cached_property    
    def season_crosses_years(self):
        return self.league_month_end <= self.league_month_start

    @cached_property
    def league_month_start(self) -> int:
        return self.sport_data["sports"][self.game.sport]["leagues"][self.game.league]["month_start"]

    @cached_property
    def league_month_end(self) -> int:
        return self.sport_data["sports"][self.game.sport]["leagues"][self.game.league]["month_end"]



def start_server():
    #pass
    app.run(host="0.0.0.0", port=8900, threaded=True)
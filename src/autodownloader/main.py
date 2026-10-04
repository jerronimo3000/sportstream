import re
from playwright.sync_api import sync_playwright,Page,Browser,Request
from dataclasses import dataclass
import re
import subprocess
import time
import requests
import streamlink
from streamlink import Streamlink
from pathlib import Path
from flask import Flask, Response, request,send_file
from streamlink.stream.stream import Stream
from .plugins import Site_plugin,Sportsurge, Dudestream
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

#logging.basicConfig(level=logging.DEBUG)
#logger=logging.getLogger("streamlink")
#logger.setLevel(logging.DEBUG)
@dataclass
class m3u8_link:
    url: str
    cookies_header: str
    all_headers: str
def match_m3u8(request) -> str:
    #print(request.url)
    pattern = r"\.m3u8(\?.*)?$"
    if re.search(pattern, request.url):
        print(f"FOUND M3U8 URL!!!: {request.url}")

def print_request_url(request: Request):
    print(f"URL: {request.url}")

def get_network_requests(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Must be False so the player initializes
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--autoplay-policy=no-user-gesture-required"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 3840, "height": 2160}
        )    

        page = browser.new_page()
        page.on("request",match_m3u8)
        page.goto(url=url,wait_until="domcontentloaded")
        page.wait_for_timeout(timeout=60000)



def get_m3u8_link(
    webpage_url: str, timeout: int = 30000, num_retries: int = 3, raise_on_missing: bool = False
) -> m3u8_link:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 3840, "height": 2160}
        )    

        page = browser.new_page()

        for i in range(num_retries):
            attempt = i+1
            try:
                print(f"opening url and waiting for m3u8 request ({webpage_url})")
                with page.expect_request(lambda req: ".m3u8" in req.url, timeout=timeout) as request_info:
                    page.goto(url=webpage_url, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)

                request = request_info.value
                all_headers = request.all_headers()
                cookies = context.cookies()
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

                print(f"FOUND M3U8 ULR: {request.url}")
                return m3u8_link(
                    url=request.url,
                    cookies_header=cookie_str,
                    all_headers=all_headers
                )
                
            except Exception as e:
                print(f"[!] Error intercepting M3U8: {e}")
                if attempt < num_retries:
                    print(f"Retrying...({attempt+1} of {num_retries})")
                else:
                    browser.close()
                    return None
        browser.close()


def get_stream(m3u8_link: m3u8_link) -> Stream:
    if not m3u8_link:
        print("[!] Invalid stream object.")
        return

    # Initialize a Streamlink session
    session = streamlink.Streamlink()

    # Configure session options/headers to pass CDN checks
    session.set_option("http-no-ssl-verify", True)
    session.set_option("http-headers", {
        "Referer": m3u8_link.referer,
        "User-Agent": m3u8_link.user_agent,
        "Cookie": m3u8_link.cookies_header
    })

    session.set_option("hls-live-restart", True)

    print(f"[+] Fetching stream tracks from manifest...")
    # Wrap with hlsvariant:// to force HLS parsing
    streams = session.streams(f"hlsvariant://{m3u8_link.url}")
    
    if "best" not in streams:
        print("[!] No valid stream variant found.")
        return

    stream = streams["best"]
    return stream

def save_stream_to_file(stream: Stream, output_file: str = "output.ts"):
    print(f"[+] Recording stream into '{output_file}'... Press Ctrl+C to stop.")
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    try:
        with stream.open() as stream_fd, open(output_file, "wb") as out_file:
            while True:
                # Read chunks from the stream and write to disk
                data = stream_fd.read(1024 * 64)
                if not data:
                    break
                out_file.write(data)
    except KeyboardInterrupt:
        print("\n[+] Recording stopped by user.")
    finally:
        print(f"[+] File saved: {output_file}")


class m3u8_url_finder:
    def __init__(self,team: str, num_retries: int = 10,plugin: Site_plugin = Sportsurge):
        self.team = team
        self.plugin = plugin()
        self.num_retries = num_retries
    
    def attempt_function(self,function: callable,arguments: dict = {}):
        attempts = 1
        while attempts <= self.num_retries:
            try:
                function_return = function(**arguments)
                return function_return
            except Exception as e:
                print(f"Error: {e} \nAttempt {attempts} of {self.num_retries} failed. Retrying...")
                attempts += 1
                if attempts > self.num_retries:
                    raise RuntimeError("Maximum number of retries reached")
            
    
    def get_game_page_url(self):
        return self.attempt_function(self.plugin.get_current_game_url,{"team_name": self.team})

    def get_m3u8_link(self):
        game_page_url = self.get_game_page_url()
        return self.attempt_function(self.get_m3u8_link_single_attempt,{"game_page_url": game_page_url})

    def get_m3u8_link_single_attempt(self,game_page_url: str) -> str:
        print("Finding a new M3U8 stream...")
        m3u8_link = get_m3u8_link(game_page_url)

        if m3u8_link is None:
            raise RuntimeError("Could not find M3U8 URL")
        else:
            return m3u8_link

def restream_m3u8_playlist(m3u8_link: m3u8_link):
    try:
        stream = get_stream(m3u8_link)

        if stream is None:
            raise RuntimeError("Could not find playable stream")

        print("Opening Streamlink stream...")
        stream_fd = stream.open()

        while True:
            data = stream_fd.read(64 * 1024)

            if not data:
                raise ConnectionError("Stream ended")

            yield data

    except Exception as e:
        print(f"Stream failed: {e!r}")
        print("Retrying in 5 seconds...")
        time.sleep(5)

    finally:
        if stream_fd is not None:
            try:
                stream_fd.close()
            except Exception:
                pass

        print("Stream connection closed")



def generate(game_page_url: str):
    while True:
        stream_fd = None

        try:
            print("Finding a new M3U8 stream...")
            m3u8_link = get_m3u8_link(game_page_url)

            if m3u8_link is None:
                raise RuntimeError("Could not find M3U8 URL")

            stream = get_stream(m3u8_link)

            if stream is None:
                raise RuntimeError("Could not find playable stream")

            print("Opening Streamlink stream...")
            stream_fd = stream.open()

            while True:
                data = stream_fd.read(64 * 1024)

                if not data:
                    raise ConnectionError("Stream ended")

                yield data

        except Exception as e:
            print(f"Stream failed: {e!r}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

        finally:
            if stream_fd is not None:
                try:
                    stream_fd.close()
                except Exception:
                    pass

            print("Stream connection closed")

def find_m3u8_link(urls: str, num_retries: int = 5):
    print("Finding a new M3U8 stream...")
    for url in urls:
        for i in range(3):
            m3u8 = get_m3u8_link(url,timeout=5000)
            if m3u8 is not None:
                break
        if m3u8 is not None:
            break

    if m3u8 is None:
        raise RuntimeError("Could not find M3U8 URL")

    return m3u8

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
    def __init__(self,game_page_url: str, m3u8_link: m3u8_link = None):
        self.game_page_url = game_page_url
        self.initialize_m3u8_variables(m3u8_link)
        self.initialize_stream_variables()
        self.initialize_session()
        self.initialize_threading()
    def initialize_m3u8_variables(self,m3u8_link: m3u8_link):
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
        self.m3u8_link = get_m3u8_link(self.game_page_url)
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
        playlist_url = stream.url
        playlist_contents = requests.get(playlist_url,headers=self.m3u8_link.all_headers)
        playlist_contents.raise_for_status()
        return(Response(
            self.condition_playlist(playlist_url,playlist_contents.text),
            mimetype="application/vnd.apple.mpegurl",
        ))

    def condition_playlist(self,base_url: str,playlist: str):
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
        self.stream_managers: dict[str, Stream_manager] = {}
        self.stream_clients: dict[int,dict[int,queue.Queue]] = {}
        self.threads: dict[int,threading.Thread] = {}
        self.lock = threading.Lock()
    def add_stream_manager(self,stream_manager: Stream_manager, stream_id: str):
        with self.lock:
            if not stream_id in self.stream_managers:
                self.stream_managers[stream_id] = stream_manager
            if not stream_id in self.stream_clients:
                self.stream_clients[stream_id] = {}
    def get_client_queues(self,stream_id: int):
        return self.stream_clients[stream_id]
    def get_client_queue_single(self,stream_id: int, client_id: int) -> queue.Queue:
        with self.lock:
            client_queue = self.get_client_queues(stream_id)[client_id]
        return client_queue
    def get_next_available_stream_id(self) -> int:
        with self.lock:
            if len(self.stream_managers) == 0:
                avaialbe_id = 0
            else:
                avaialbe_id = max(self.stream_managers.keys()) + 1
        return avaialbe_id
    def get_next_available_client_id(self,stream_id: int) -> int:
        with self.lock:
            if not stream_id in self.stream_clients:
                avaialbe_id = 0
            elif len(self.stream_clients[stream_id]) == 0:
                avaialbe_id = 0
            else:
                avaialbe_id = max(self.stream_clients[stream_id].keys()) + 1
        return avaialbe_id
    def add_client(self,stream_id: str, client_id: int):
        with self.lock:
            first_client = len(self.stream_clients[stream_id]) == 0
            self.stream_clients[stream_id][client_id] = queue.Queue()
        if first_client:
            fill_thread = threading.Thread(
                    target=self.fill_client_queues,
                    args=(stream_id,),
                    name=f"queue_fill_{stream_id}",
                    daemon=True
                )
            self.threads[stream_id] = fill_thread
            fill_thread.start()
        
    def remove_client(self,stream_id: int, client_id: int):
        with self.lock:
            self.stream_clients[stream_id].pop(client_id,None)

    def fill_client_queues(self,stream_id: int):
        with self.lock:
            stream_manager = self.stream_managers[stream_id]
        try:
            for chunk in stream_manager.stream():
                with self.lock:
                    client_queues = self.get_client_queues(stream_id=stream_id)
                for client_queue in client_queues.values():
                    try:
                        client_queue.put_nowait(chunk)
                    except queue.Full:
                        try:
                            client_queue.get_nowait()
                            client_queue.put_nowait(chunk)
                        except (queue.Empty, queue.Full):
                            pass
        finally:
            with self.lock:
                self.threads.pop(stream_id)



    def stream(self,stream_id: str, client_id: int):
        client_queue = self.get_client_queue_single(stream_id,client_id)
        try:
            while True:
                try:
                    chunk = client_queue.get(timeout=2.0)
                    yield chunk
                except queue.Empty:
                    continue
        except GeneratorExit:
            print(f"Client {client_id} disconnected from stream {stream_id}")
        finally:
            self.remove_client(stream_id,client_id)
            self.stop_stream_if_no_clients(stream_id)
    
    def stop_stream_if_no_clients(self,stream_id: int):
        with self.lock:
            num_clients = len(self.stream_clients[stream_id])
            if num_clients == 0:
                self.stream_managers[stream_id].close_all_streams()
    

    

COORDINATOR = Stream_coordinator()

@app.get("/<string:sport>/<int:channel_index>")
def restream(sport: str, channel_index: int):
    if request.method == "HEAD":
        return Response(status=200, mimetype="video/mp2t")
    user_agent = request.headers.get("User-Agent", "")
    print(f"USER AGENT: {user_agent}")
    print(f"This is the sport: {sport}", flush=True)
    game_retriever = Game_data_manager(sport,channel_index)
    try:
        active_team = game_retriever.currently_playing_team
        #active_team = "athletics"
        if not active_team:
            print(f"No active game found for {sport} on channel slot {channel_index}", flush=True)
            return Response("No active game scheduled right now.", status=404, mimetype="text/plain")


        game_data_manager = Game_data_manager(sport,channel_index)
        m3u8_retriever = m3u8_url_finder(team=active_team)
        if not game_data_manager.get_cached_game_url() == "":
            game_page_url = game_data_manager.get_cached_game_url()
        else:
            game_page_url = m3u8_retriever.get_game_page_url()
            game_data_manager.write_m3u8_info(game_page_url=game_page_url)
        game = game_data_manager.active_game
        if not game.id in COORDINATOR.stream_managers:
            stream = Stream_manager(game_page_url=game_page_url)
            COORDINATOR.add_stream_manager(stream,game.id)
        client_id = COORDINATOR.get_next_available_client_id(game.id)
        COORDINATOR.add_client(game.id,client_id)   
        #if is_recording_request(user_agent):
            #print(f"Attempting to record {active_team}")
            #m3u8_link = m3u8_retriever.get_m3u8_link()
            #stream = attempt_function(get_stream,{"m3u8_link": m3u8_link},sleep_time=5)
            #recording_writer = Recording_writer(game_data_manager.active_game)

            #output_file = f"/run/media/system/Games/media_share/TV Shows/{recording_writer.recording_end_filepath()}"
            #save_stream_to_file(stream,output_file=output_file)
        #else:
        return Response(COORDINATOR.stream(game.id,client_id), mimetype="video/mp2t")

    except Exception as e:
        print(f"ERROR: {e}")
        return Response("Not Found", status=404)

DEVELOPMENT_MANAGER = Stream_manager("https://www.earthcam.com/world/spain/tamariu/?cam=tamariu")
@app.get("/development")
def development():
    if request.method == "HEAD":
        return Response(status=200, mimetype="application/vnd.apple.mpegurl")

    return DEVELOPMENT_MANAGER.get_playlist()



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

@app.route("/channels.m3u", methods=["GET"])
def get_channels_m3u():
    m3u_path = Path(__file__).resolve().parent / "data/channels.m3u"
    if not os.path.exists(m3u_path):
        return Response("#EXTM3U\n", mimetype="audio/x-mpegurl"), 404
    return send_file(m3u_path, mimetype="audio/x-mpegurl")

def get_schedule() -> dict:
    with open(Constants.schedule_file, "r") as f:
        data = json.load(f)
    return data

def get_team_data() -> dict:
    with open(Constants.team_data, "r") as f:
        data = json.load(f)
    return data

def get_sport_data() -> dict:
    with open(Constants.sport_data, "r") as f:
        data = json.load(f)
    return data

@dataclass
class Team:
    name: str
    sport: str
    league: str

@dataclass
class Game:
    sport: str
    league: str
    team_1: str
    team_2: str
    time_start: datetime
    time_end: datetime
    id: str
    game_page_url: str = ""


class Game_data_manager:
    def __init__(self,sport: str, channel: int, search_time: datetime | None = datetime.now(timezone.utc)):
        self.sport = sport
        self.channel = str(channel)
        self.search_time = search_time
    
    @cached_property
    def schedule(self):
        return get_schedule()
    
    @cached_property
    def team_data(self):
        return get_team_data()

    def get_cached_game_url(self) -> str:
        return self.active_game.game_page_url
    
    def write_m3u8_info(self,game_page_url: str):
        # self.schedule[self.sport]["channels"][self.channel]["games"][self.active_game_index]["m3u8_info"] = {
        #     "url": m3u8_link.url,
        #     "referer": m3u8_link.referer,
        #     "cookies_header": m3u8_link.cookies_header,
        #     "user_agent": m3u8_link.user_agent
        # }
        self.schedule[self.sport]["channels"][self.channel]["games"][self.active_game_index]["game_page_url"] = game_page_url

        with open(Constants.schedule_file, "w") as f:
            json.dump(self.schedule, f, indent=4)

    @cached_property
    def active_game_index(self) -> int:
        games = self.find_possible_games()
        for i,game in enumerate(games):
            if self.game_is_on_now(game):
                return i
       
    @cached_property
    def active_game(self) -> Game:
        print(f"finding team playing {self.sport} on channel {self.channel}")
        games = self.find_possible_games()
        for game in games:
            if self.game_is_on_now(game):
                league = self.team_data[game["team_1"]]["league"]
                active_game = Game(sport=self.sport,league=league,**game)
        try:
            return active_game
        except Exception as e:
            print(e)
            print("Could not find game")

    @cached_property
    def currently_playing_team(self) -> str:
        game = self.active_game
        return game.team_1

    def game_is_on_now(self,game: dict) -> bool:
        time_start = datetime.fromisoformat(game["time_start"])
        time_end = datetime.fromisoformat(game["time_end"])

        return time_start <= self.search_time and time_end >= self.search_time

    def find_possible_games(self):
        games = self.schedule[self.sport]["channels"][self.channel]["games"]
        return games

def convert_to_str_with_leading_zeroes(num: int,output_digits: int) -> str:
    num_str = str(num)
    if len(num_str) >= output_digits:
        formatted_num = num_str
    else:
        leading_zeroes = ["0"]*(output_digits - len(num_str))
        formatted_num = "".join([*leading_zeroes,num_str])
    return formatted_num

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



#url = "https://v2.streameast.ga/mlb/philadelphia-phillies-vs-seattle-mariners-2/"
#m3u8 = get_m3u8_url(url)
#print(m3u8.referer)
#print(m3u8.url)
#m3u8_retriever = m3u8_url_finder("nationals")
#m3u8_link = m3u8_retriever.get_m3u8_link()
#stream = get_stream(m3u8_link=m3u8_link)
#save_stream_to_file(stream=stream)
#finder = m3u8_url_finder("cardinals")
#print(finder.get_m3u8_url())

def start_server():
    #pass
    app.run(host="0.0.0.0", port=8900, threaded=True)
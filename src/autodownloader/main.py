import re
from playwright.sync_api import sync_playwright,Page,Browser,Request
from dataclasses import dataclass
import re
import subprocess
import time
import requests
import streamlink
from pathlib import Path
from flask import Flask, Response, request,send_file
from streamlink.stream.stream import Stream
from plugins import Site_plugin,Sportsurge, Dudestream
import os
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from functools import cached_property
import json
from zoneinfo import ZoneInfo
from constants import Constants

app = Flask(__name__)


@dataclass
class m3u8_link:
    url: str
    referer: str
    user_agent: str
    cookies_header: str

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
    url: str, timeout: int = 20000, raise_on_missing: bool = False
) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Must be False so the player initializes
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

        try:
            print(f"opening url and waiting for m3u8 request ({url})")
            with page.expect_request(lambda req: ".m3u8" in req.url, timeout=timeout) as request_info:
                page.goto(url=url, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)

            request = request_info.value
            referer = request.headers.get("referer", url)
            user_agent = request.headers.get("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")

            cookies = context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

            print(f"FOUND M3U8 ULR: {request.url}")
            return m3u8_link(
                url=request.url,
                referer=referer,
                user_agent=user_agent,
                cookies_header=cookie_str
            )
            
        except Exception as e:
            print(f"[!] Error intercepting M3U8: {e}")
            return None
        finally:
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
            m3u8 = get_m3u8_url(url,timeout=5000)
            if m3u8 is not None:
                break
        if m3u8 is not None:
            break

    if m3u8 is None:
        raise RuntimeError("Could not find M3U8 URL")

    return m3u8

@app.get("/<string:sport>/<int:channel_index>")
def restream(sport: str, channel_index: int):
    user_agent = request.headers.get("User-Agent", "")
    print(f"USER AGENT: {user_agent}")
    print(f"This is the sport: {sport}", flush=True)
    game_retriever = Game_data_manager(sport,channel_index)
    active_team = game_retriever.currently_playing_team
    #active_team = "athletics"
    if not active_team:
        print(f"No active game found for {sport} on channel slot {channel_index}", flush=True)
        return Response("No active game scheduled right now.", status=404, mimetype="text/plain")

    print(f"{active_team} are playing {sport} right now", flush=True)

    game_data_manager = Game_data_manager(sport,channel_index)
    try:
        game_page_url = game_data_manager.get_cached_game_url()
    except:
        m3u8_retriever = m3u8_url_finder(active_team)
        game_page_url = m3u8_retriever.get_game_page_url()
        #m3u8_link = m3u8_retriever.get_m3u8_link()
        game_data_manager.write_m3u8_info(game_page_url=game_page_url)
    return Response(generate(game_page_url=game_page_url), mimetype="video/mp2t")

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

class Game_data_manager:
    def __init__(self,sport: str, channel: int, search_time: datetime | None = datetime.now(timezone.utc)):
        self.sport = sport
        self.channel = str(channel)
        self.search_time = search_time
    
    @cached_property
    def schedule(self):
        return get_schedule()

    def get_cached_game_url(self) -> str:
        return self.active_game["game_page_url"]
    
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
    def active_game(self) -> dict:
        print(f"finding team playing {self.sport} on channel {self.channel}")
        games = self.find_possible_games()
        for game in games:
            if self.game_is_on_now(game):
                return game

    @cached_property
    def currently_playing_team(self) -> str:
        game = self.active_game
        return game["team_1"]

    def game_is_on_now(self,game: dict) -> bool:
        time_start = datetime.fromisoformat(game["time_start"])
        time_end = datetime.fromisoformat(game["time_end"])

        return time_start <= self.search_time and time_end >= self.search_time

    def find_possible_games(self):
        games = self.schedule[self.sport]["channels"][self.channel]["games"]
        return games

    
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

if __name__ == "__main__":
    #pass
    app.run(host="0.0.0.0", port=8900)
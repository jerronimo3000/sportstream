from playwright.sync_api import sync_playwright,Page,Browser,Request
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import ClassVar
import json
from pathlib import Path
from .game_data import Game
from functools import cached_property
import shutil
import subprocess
import re
from flask import Response
import time





@dataclass
class Playlist_request:
    url: str
    cookies_header: str
    all_headers: str
class Stream_repackager:
    segment_parent_dir: ClassVar[Path] = Path("/dev/shm/sportstream")
    host_address: ClassVar[str] = "http://192.168.50.109:8900"

    def __init__(self,stream_id: str, playlist_request: Playlist_request):
        self.initialize_state_vars()
        self.stream_id = stream_id
        self.playlist_request = playlist_request
        self.set_output_dir()
        self.start()

    def initialize_state_vars(self):
        self.ffmpeg = None

    def set_output_dir(self):
        self.output_dir = self.segment_parent_dir / f"{self.stream_id}/"

    def start(self):
        self.remove_files()
        self.ffmpeg = self._start_ffmpeg()
    def stop(self):
        if self.ffmpeg is None:
            print(f"ffmpeg not started for stream id {self.stream_id}")
        else:
            self.ffmpeg.terminate()
            self.remove_files()

    def remove_files(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)
    def _start_ffmpeg(self):
        output_dir = Path(self.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        headers = dict(self.playlist_request.all_headers)         # copy, so the object's own dict isn't modified
        headers["Cookie"] = self.playlist_request.cookies_header.strip()
        header_string = "".join(f"{name}: {value}\r\n" for name, value in headers.items())

        
        command = [
            "ffmpeg", "-loglevel", "warning", "-y", "-nostdin",
            "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
            "-allowed_extensions", "ALL",
            "-extension_picky", "0",
            "-headers", header_string,
            "-i", self.playlist_request.url,
            "-c", "copy",
            "-f", "hls",
            "-hls_segment_type", "mpegts",
            "-hls_time", "4",
            "-hls_list_size", "10",
            "-hls_flags", "delete_segments+temp_file+omit_endlist",
            "-hls_segment_filename", str(self.output_dir / "seg_%08d.ts"),
            str(output_dir / "index.m3u8"),
        ]

        return subprocess.Popen(command)

    @property
    def playlist(self) -> str:
        playlist_ffmpeg = self.get_ffmpeg_playlist()
        new_playlist_lines = []
        for line in playlist_ffmpeg:
            if self.is_segment_line(line):
                id = self.get_segment_id(line)
                new_playlist_lines.append(
                    f"{self.host_address}/playlist/{self.stream_id}/segments/{id}.ts"
                )
            else:
                new_playlist_lines.append(line.strip())
        playlist = "\n".join(new_playlist_lines)
        return playlist

    def is_segment_line(self,line: str) -> bool:
        return line.startswith("seg")
    def get_segment_id(self, line: str) -> str:
        pattern = r"seg_(\d+).ts$"
        match = re.search(pattern,line)
        if match:
            return match.group(1)

    def get_ffmpeg_playlist(self) -> list[str]:
        with open(self.output_dir / "index.m3u8", "r") as f:
            playlist = f.readlines()
        return playlist

    def serve_segment(self,segment_id: str):
        filepath = self.output_dir / f"seg_{segment_id}.ts"
        return Response(
            read_file_chunks(filepath),
            headers={"Content-Type": "video/mp2t"}
        )


class Site_plugin(ABC):
    def __init__(self,game: Game):
        self.game = game
        self.initialize_vars()

    def initialize_vars(self):
        self._page = None
        self._playlist_request = None
        self._stream_repackager = None

    @property
    def page(self) -> Page:
        if self._page is None:
            self._page = self.instantiate_page()
        return self._page

    def instantiate_page(self) -> Page:
        p = sync_playwright().start()
        browser = p.chromium.launch(
            headless=False,
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
        return context.new_page()
    
    @property
    def stream_repackager(self) -> Stream_repackager:
        if self._stream_repackager is None:
            self._stream_repackager = Stream_repackager(self.game.id,self.get_playlist_request())
        return self._stream_repackager
    
    @abstractmethod
    def get_playlist_request(self) -> Playlist_request:
        pass

    def get_playlist_local(self) -> str:
        return self.stream_repackager.playlist


class Development(Site_plugin):
    def __init__(self,stream_page_url: str):
        self.stream_page_url = stream_page_url
        super().__init__(game=Game(
            "development",
            "development",
            "team_dev_1",
            "team_dev_2",
            "now",
            "later",
            "development"
        ))

    def get_playlist_request(self) -> Request:
        page = self.instantiate_page()
        try:
            playlist = get_playlist_request(
                intercept_playlist_request(page,self.stream_page_url,".m3u8"),
                page
            )

        except:
            playlist = get_playlist_request(
                intercept_playlist_request(page,self.stream_page_url,"application"),
                page
            )


        return playlist
class Dudestream(Site_plugin):
    base_url = "https://dudestream1.com/"
    league_urls: ClassVar[dict[str,str]] = {
        'MLB': f"{base_url}/category/mlb",
        'soccer': f"{base_url}/category/soccer"
    }
    def get_current_game_url(self,team_name: str) -> str:
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
            page.goto(self.league_urls['soccer'])

            link = page.locator(f"a:has-text('{team_name}')").first
            game_url = link.get_attribute("href")
            browser.close()
            return game_url

class Sportsurge(Site_plugin):
    base_url: ClassVar[dict[str,str]] = {
        "development": "https://soccersurge.io/#",
        "soccer": "https://soccersurge.io/",
        "basketball": "https://v2.sportsurge.net/watch-basketball-streams/",
        "baseball": "https://v2.sportsurge.net/watch-baseball-streams/",
        "NFL": "https://v2.sportsurge.net/watch-nfl-streams/",
    }
     
    preferred_sites: ClassVar[dict[str,list[str]]] = {
        "soccer": ["tvsportslive","iframely","socowatch"],
        "NFL": ["tvsportslive","streameast"]
    }

    def __init__(self):
        self.set_team_data()
    
    def set_team_data(self):
        team_data_path = Path(__file__).resolve().parent / "data/team_data.json"
        with open(team_data_path,"r") as f:
            self.team_data = json.load(f)

    def get_base_url(self,team_name: str) -> str:
        team_data = self.team_data[team_name]
        if team_data["sport"] in self.base_url:
            base_url = self.base_url[team_data["sport"]]
        elif team_data["league"] in self.base_url:
            base_url = self.base_url[team_data["league"]]
        else:
            raise ValueError(f"[ERROR] Team {team_name}'s sport ({team_data["sport"]}) and league ({team_data["league"]}) not configured in plugin")
        return base_url

    def get_current_game_url(self,team_name: str,provider: str = None,retries: int = 10) -> str:
         print("LOG: getting current game url (Sportsuge.get_current_game_url()")
         with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=False)
            context = browser.new_context(no_viewport=True)
            page = context.new_page()
            base_url = self.get_base_url(team_name=team_name)
            print(base_url)
            page.goto(base_url, wait_until="domcontentloaded")
            try:
                page.wait_for_function(
                    "() => !document.title.includes('Just a moment')",
                    timeout=20000,
                )
            except Exception:
                page.screenshot(path="challenge_stuck.png")
                raise RuntimeError("Challenge did not clear on its own (likely interactive)")
            page.screenshot(path="debug_error.png")
            with open("page_content.html","w") as f:
                f.write(page.content())

            # 2. Safely normalize team_name to lowercase for URL matching
            clean_team_name = team_name.lower().strip()

            # 3. Explicitly wait for the match card to exist before attempting to click
            target_match = page.locator(f"a.match-row[href*='{clean_team_name}']").first
            target_match.wait_for(state="visible", timeout=10000)
            with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                target_match.click()
            streaming_site_elems_search = page.locator("div.stream-item").filter(has_text=provider)
            if streaming_site_elems_search.count() > 0:
                game_url = streaming_site_elems_search.first.get_attribute("data-href")
            else:
                raise ValueError("could not find streaming site")
                browser.close()
            return game_url



    def get_current_game_url_all(self,team_name: str,provider: str = None,retries: int = 10) -> str:
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

            page.goto(self.get_base_url(team_name=team_name))

            with page.expect_navigation(wait_until="domcontentloaded",timeout=10000):
                page.locator("a").filter(has_text=team_name).first.click(timeout=10000)

            streaming_site_elems_search = page.locator("div.stream-item").filter(has_text=provider)
            if streaming_site_elems_search.count() > 0:
                game_url = [elem.get_attribute("data-href") for elem in streaming_site_elems_search.all()]
            else:
                raise ValueError("could not find streaming site")
                browser.close()
            return game_url




class Nbabite(Site_plugin):
    base_url: ClassVar[dict[str,str]] = {
        "development": "https://soccersurge.io/#",
        "soccer": "https://soccersurge.io/",
        "basketball": "https://nbabitez.com/",
        "baseball": "https://v2.sportsurge.net/watch-baseball-streams/",
        "NFL": "https://v2.sportsurge.net/watch-nfl-streams/",
    }
     
    preferred_sites: ClassVar[dict[str,list[str]]] = {
        "soccer": ["tvsportslive","iframely","socowatch"],
        "NFL": ["tvsportslive","streameast"]
    }

    def __init__(self):
        self.set_team_data()
    
    def set_team_data(self):
        team_data_path = Path(__file__).resolve().parent / "data/team_data.json"
        with open(team_data_path,"r") as f:
            self.team_data = json.load(f)

    def get_base_url(self,team_name: str) -> str:
        team_data = self.team_data[team_name]
        if team_data["sport"] in self.base_url:
            base_url = self.base_url[team_data["sport"]]
        elif team_data["league"] in self.base_url:
            base_url = self.base_url[team_data["league"]]
        else:
            raise ValueError(f"[ERROR] Team {team_name}'s sport ({team_data["sport"]}) and league ({team_data["league"]}) not configured in plugin")
        return base_url

    def get_current_game_url(self,team_name: str,provider: str = None,retries: int = 10) -> str:
         print("LOG: getting current game url (Nbabite.get_current_game_url()")
         with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=False)
            context = browser.new_context(no_viewport=True)
            page = context.new_page()
            base_url = self.get_base_url(team_name=team_name)
            print(base_url)
            page.goto(base_url)
            try:
                page.wait_for_function(
                    "() => !document.title.includes('Just a moment')",
                    timeout=20000,
                )
            except Exception:
                page.screenshot(path="challenge_stuck.png")
                raise RuntimeError("Challenge did not clear on its own (likely interactive)")
            page.screenshot(path="debug_error.png")
            with open("page_content.html","w") as f:
                f.write(page.content())
            game_elem = page.locator("a").filter(has=page.locator("p.team-p", has_text=team_name)).first
            game_site_list_url = f"https://nbabitez.com{game_elem.get_attribute("href")}"

            print(f"Found game site list: {game_site_list_url}")
            page.goto(game_site_list_url)
            page.screenshot(path="debug_error_2.png")
            streaming_site_elems_search = page.locator("input").filter(has_text=provider)
            if streaming_site_elems_search.count() > 0:
                game_url = streaming_site_elems_search.first.get_attribute("value")
                print(f"Found game url: {game_url}")
            else:
                raise ValueError("could not find streaming site")
                browser.close()
            return game_url



    def get_current_game_url_all(self,team_name: str,provider: str = None,retries: int = 10) -> str:
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

            page.goto(self.get_base_url(team_name=team_name))

            with page.expect_navigation(wait_until="domcontentloaded",timeout=10000):
                game_elem = page.locator("a").filter(has_text=team_name).first
                game_site_list_url = game_elem.get_attribute("href")

            page.goto(game_site_list_url)

            streaming_site_elems_search = page.locator("div.stream-item").filter(has_text=provider)
            if streaming_site_elems_search.count() > 0:
                game_url = [elem.get_attribute("data-href") for elem in streaming_site_elems_search.all()]
            else:
                raise ValueError("could not find streaming site")
                browser.close()
            return game_url


class Streameast(Site_plugin):
    game_page_url_prefix: ClassVar[str] = "https://v2.streameast.ga"
    base_url: ClassVar[dict[str,str]] = {
        "development": "https://soccersurge.io/#",
        "soccer": "https://v2.streameast.ga/soccer-streams",
        "basketball": "https://v2.streameast.ga/nba-streams",
        "baseball": "https://v2.streameast.ga/mlb-streams",
        "NFL": "https://v2.streameast.ga/nfl-streams",
    }
     
    def __init__(self):
        self.set_team_data()    

    def set_team_data(self):
        team_data_path = Path(__file__).resolve().parent / "data/team_data.json"
        with open(team_data_path,"r") as f:
            self.team_data = json.load(f)

    def get_base_url(self,team_name: str) -> str:
        team_data = self.team_data[team_name]
        if team_data["sport"] in self.base_url:
            base_url = self.base_url[team_data["sport"]]
        elif team_data["league"] in self.base_url:
            base_url = self.base_url[team_data["league"]]
        else:
            raise ValueError(f"[ERROR] Team {team_name}'s sport ({team_data["sport"]}) and league ({team_data["league"]}) not configured in plugin")
        return base_url

    def get_current_game_url(self,team_name: str,provider: str = None,retries: int = 10) -> str:
         print("LOG: getting current game url (Streameast.get_current_game_url()")
         with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=False)
            context = browser.new_context(no_viewport=True)
            page = context.new_page()
            base_url = self.get_base_url(team_name=team_name)
            print(base_url)
            page.goto(base_url)
            #page.screenshot("base_url.out")
            try:
                page.wait_for_function(
                    "() => !document.title.includes('Just a moment')",
                    timeout=20000,
                )
            except Exception:
                page.screenshot(path="challenge_stuck.png")
                raise RuntimeError("Challenge did not clear on its own (likely interactive)")

            game_page_elem = page.locator(f'a.m-card__link[href*="{team_name}" i]').first
            
            if not game_page_elem is None:
                game_url_relative = game_page_elem.get_attribute("href")
                game_url = f"{self.game_page_url_prefix}{game_url_relative}"
                print(f"Found game url: {game_url}")
            else:
                raise ValueError("could not find streaming site")
                browser.close()
            return game_url



class Sportusa(Site_plugin):
    game_page_url_prefix: ClassVar[str] = "https://v2.streameast.ga"
    base_url: ClassVar[dict[str,str]] = {
        "development": "https://soccersurge.io/#",
        "soccer": "https://v2.streameast.ga/soccer-streams",
        "basketball": "https://sportsupa.st/",
        "baseball": "https://v2.streameast.ga/mlb-streams",
        "NFL": "https://sportsupa.st/",
    }
     
    def __init__(self):
        self.set_team_data()    

    def set_team_data(self):
        team_data_path = Path(__file__).resolve().parent / "data/team_data.json"
        with open(team_data_path,"r") as f:
            self.team_data = json.load(f)

    def get_base_url(self,team_name: str) -> str:
        team_data = self.team_data[team_name]
        if team_data["sport"] in self.base_url:
            base_url = self.base_url[team_data["sport"]]
        elif team_data["league"] in self.base_url:
            base_url = self.base_url[team_data["league"]]
        else:
            raise ValueError(f"[ERROR] Team {team_name}'s sport ({team_data["sport"]}) and league ({team_data["league"]}) not configured in plugin")
        return base_url

    def get_current_game_url(self,team_name: str,provider: str = None,retries: int = 10) -> str:
         print("LOG: getting current game url (Streameast.get_current_game_url()")
         with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=False)
            context = browser.new_context(no_viewport=True)
            page = context.new_page()
            base_url = self.get_base_url(team_name=team_name)
            print(base_url)
            page.goto(base_url)
            #page.screenshot("base_url.out")
            try:
                page.wait_for_function(
                    "() => !document.title.includes('Just a moment')",
                    timeout=20000,
                )
            except Exception:
                page.screenshot(path="challenge_stuck.png")
                raise RuntimeError("Challenge did not clear on its own (likely interactive)")

            game_tile_elem = page.locator(f'').filter(has_text=f"{team_name}").first.click()
            game_page_elem = page.locator(f'a.stream-btn[href*="{team_name}" i]').first
            



            if not game_page_elem is None:
            
                game_url_relative = game_page_elem.get_attribute("href")
                game_url = f"{self.game_page_url_prefix}{game_url_relative}"
                print(f"Found game url: {game_url}")
            else:
                raise ValueError("could not find streaming site")
                browser.close()
            return game_url

class Crackstreams(Site_plugin):
    game_page_url_prefix: ClassVar[str] = "https://crackstreams.mx"
    base_urls: ClassVar[dict[str,str]] = {
        "development": "https://soccersurge.io/#",
        "basketball": "https://crackstreams.mx/league/nbastreams",
        "NFL": "https://crackstreams.mx/league/nflstreams",
    }
     
    @property 
    def base_url(self) -> str:
        sport = self.game.sport
        return self.base_urls[sport]

    @cached_property
    def stream_page_url(self) -> str:
        page = self.page
        page.goto(self.base_url)
        game_elem = self.get_game_card_elem()
        game_page_url_suffix = game_elem.get_attribute("href")
        game_page_url = self.game_page_url_prefix + game_page_url_suffix
        return game_page_url

    def get_game_card_elem(self):
        elem = self.page.locator("a.card").filter(has_text=self.game.team_1).filter(has_text=self.game.team_2).first
        return elem

    def get_playlist_request(self) -> Playlist_request:
        return get_playlist_request(self._intercept_playlist_request(), self.page)

    def _intercept_playlist_request(self) -> Request:
        return intercept_playlist_request(self.page,self.stream_page_url,"application") 





def clean_headers(headers: dict[str,str]) -> str:
    clean_headers = {
        k: v for k, v in headers.items()
        if not k.startswith(":") and k not in ("host", "content-length")
    }
    return clean_headers

def build_headers_str(headers: dict[str,str]) -> str:
    return "".join(f"{k}: {v}\r\n" for k,v in headers.items())

def get_playlist_request(raw_request: Request, page: Page) -> Playlist_request:
    url = raw_request.url
    headers = clean_headers(raw_request.all_headers())
    cookies = page.context.cookies()
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

    print(f"FOUND PLAYLIST URL: {raw_request.url}")
    return Playlist_request(
        url=url,
        cookies_header=cookie_str,
        all_headers=headers
    )

def intercept_playlist_request(page,url: str,match_string: str) -> Request:
    print("Intercepting playlist request...")
    time.sleep(1)
    with page.expect_request(lambda r: match_string in r.url) as req_info:
        page.goto(url)
    print(req_info)
    return req_info.value

def read_file_chunks(path):
    with open(path, "rb") as f:
        while chunk := f.read(188*100):
            yield chunk

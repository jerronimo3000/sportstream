from playwright.sync_api import sync_playwright
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import ClassVar
import json
from pathlib import Path


class Site_plugin(ABC):
    @abstractmethod
    def get_current_game_url(self) -> str:
        pass

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
        "any": "https://v2.sportsurge.net/",
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
from playwright.sync_api import sync_playwright
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import ClassVar

class Site_plugin(ABC):
    @abstractmethod
    def get_current_game_url(self) -> str:
        pass

class Dudestream(Site_plugin):
    league_urls: ClassVar[dict[str,str]] = {
        'MLB': "https://dudestream1.com/category/mlb/"
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
            page.goto(self.league_urls['MLB'])

            link = page.locator(f"a:has-text('{team_name}')").first
            game_url = link.get_attribute("href")
            browser.close()
            return game_url


site = Dudestream()
print(site.get_current_game_url(team_name="Cubs"))
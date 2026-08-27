from playwright.sync_api import sync_playwright
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import ClassVar

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
    base_url: ClassVar[str] = "https://v2.sportsurge.net/"
    base_url_NFL: ClassVar[str] = "https://v2.sportsurge.net/watch-nfl-streams/"
    preferred_sites: ClassVar[dict[str,list[str]]] = {
        "soccer": ["tvsportslive","iframely","socowatch"],
        "NFL": ["tvsportslive","streameast"]
    }

    def get_current_game_url(self,team_name: str,provider: str = None) -> str:
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
            page.goto(self.base_url_NFL)

            #streaming_list_elem = page.locator("a").filter(has_text=team_name).first
            with page.expect_navigation(wait_until="domcontentloaded"):
                page.locator("a").filter(has_text=team_name).first.click()
            #stream_list_appendix = streaming_list_elem.get_attribute("href")
            #stream_list_url = f"{self.base_url}/{stream_list_appendix}"
            #print(stream_list_url)

            #page.goto(stream_list_url)

            sport = "NFL"
            if provider is None:
                game_url = []
                for site in self.preferred_sites[sport]:
                    streaming_site_elems_search = page.locator("div.stream-item").filter(has_text=site)
                    if streaming_site_elems_search.count() > 0:
                        game_url.append(streaming_site_elems_search.first.get_attribute("data-href"))
                    else:
                        raise ValueError("could not find streaming site")
            else:
                streaming_site_elems_search = page.locator("div.stream-item").filter(has_text=provider)
                if streaming_site_elems_search.count() > 0:
                    game_url = streaming_site_elems_search.first.get_attribute("data-href")
                else:
                    raise ValueError("could not find streaming site")
            browser.close()


            return game_url       

#site = Sportsurge()
#print(site.get_current_game_url(team_name="KUPS KUOPIO"))
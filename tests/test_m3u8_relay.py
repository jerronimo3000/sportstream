from autodownloader import Stream_manager
from autodownloader.main import app
from pytest import fixture
import time

@fixture
def site_url() -> str:
    return "https://www.earthcam.com/usa/texas/dallas/reuniontower/?cam=reuniontower"

def test_m3u8_playlist_retrieval(site_url):
    manager = Stream_manager(site_url)
    print(manager.get_playlist())
    time.sleep(3)
    print("Getting playlist again...")
    print(manager.get_playlist())

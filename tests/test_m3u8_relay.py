from autodownloader import Stream_manager,Stream_coordinator
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

def test_segment_url_replacement(site_url):
    coordinator = Stream_coordinator()
    manager = Stream_manager(site_url)
    coordinator.add_stream_manager(manager,1)
    print(coordinator.get_local_playlist(1))

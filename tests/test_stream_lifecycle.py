from autodownloader import *
from pytest import fixture
import time

@fixture
def livestream_site() -> str:
    return "https://abc.com/watch-live/784b058c-3aee-4ec9-a6d3-754ba6e4dbac"
    #return "https://v2.streameast.ga/mlb/tampa-bay-rays-vs-new-york-yankees-4/"
@fixture
def m3u8_link(livestream_site) -> str:
    m3u8_link = get_m3u8_link(livestream_site)
    return m3u8_link

@fixture
def stream_manager(m3u8_link):
    return Stream_manager(m3u8_link)



def test_stream_metadata_acquisition(stream_manager):
    for i in range(6):
        stream_manager.update_cached_streams()
        time.sleep(3)

def test_stream_connection_state_transition(stream_manager):
    stream_manager.update_cached_streams()
    stream_manager.stream()
    stream_manager.close_all_streams()
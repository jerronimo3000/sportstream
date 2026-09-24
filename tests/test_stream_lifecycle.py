from autodownloader import *
from pytest import fixture
import time

@fixture
def livestream_site() -> str:
    return "https://www.earthcam.com/usa/texas/dallas/reuniontower/?cam=reuniontower"
    #return "https://v2.streameast.ga/mlb/tampa-bay-rays-vs-new-york-yankees-4/"
@fixture
def m3u8_link(livestream_site) -> str:
    m3u8_link = get_m3u8_link(livestream_site)
    return m3u8_link

@fixture
def stream_manager(livestream_site):
    return Stream_manager(game_page_url=livestream_site)

def test_stream_connection_state_transition(stream_manager):
    stream_manager.update_cached_streams()
    stream_manager.stream()
    stream_manager.close_all_streams()

def test_stream_warmer(stream_manager):
    start_time = time.perf_counter() 
    while time.perf_counter() - start_time < 10:
        pass
    stream_manager._stream()
    stream_manager.stop_threading()
    assert stream_manager.cached_streams is not None

def test_stream_on_demand_fetch(stream_manager):
    stream_manager.stream()
    stream_manager.close_all_streams()
    assert stream_manager.cached_streams is not None

def test_stream(stream_manager):
    time_start = time.perf_counter()
    while time.perf_counter() - time_start < 5:
        stream = stream_manager.stream()
        data = next(stream)
        assert data is not None

@fixture
def stream_coordinator():
    return Stream_coordinator()

def test_stream_game(stream_coordinator,stream_manager):
    stream_coordinator.add_stream_manager(stream_manager,1)
    stream = stream_coordinator.stream(game_id=1)
    data = next(stream)
    print(data)
    assert data is not None
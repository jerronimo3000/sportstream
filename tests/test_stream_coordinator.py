from pytest import fixture
from autodownloader import *

from test_stream_lifecycle import stream_manager

@fixture
def stream_coordinator():
    return Stream_coordinator()

def test_stream_game(stream_coordinator,stream_manager):
    stream_coordinator.add_stream_manager(stream_manager,1)

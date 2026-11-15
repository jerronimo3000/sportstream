from autodownloader.plugins import Crackstreams,Streameast
import pytest
from pytest import fixture
from autodownloader.game_data import Game

def test_crackstreams():
    game = Game(
        sport = "basketball",
        league = "NBA",
        team_1="NBA",
        team_2="24/7",
        time_start="123456",
        time_end="78910",
        id="12345"
    )
    site = Crackstreams(game=game)
    assert site.stream_page_url == "https://crackstreams.mx/stream/nba-24-7-live-stream"
    #print(site.get_playlist_local())

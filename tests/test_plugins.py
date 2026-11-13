from autodownloader.plugins import Crackstreams,Streameast
import pytest
from pytest import fixture
from autodownloader.game_data import Game

def test_crackstreams():
    game = Game(
        sport = "basketball",
        league = "NBA",
        team_1="pistons",
        team_2="wizards",
        time_start="123456",
        time_end="78910",
        id="12345"
    )
    site = Crackstreams(game=game)
    assert site.game_page_url == "https://crackstreams.mx/stream/detroit-pistons-vs-washington-wizards"
    #site.get_playlist_local()

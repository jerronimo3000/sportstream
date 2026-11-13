from autodownloader.plugins import Crackstreams,Streameast
import pytest
from pytest import fixture

def test_crackstreams():
    site = Crackstreams(game=game)
    site.game_page_url
    site.get_playlist_local()

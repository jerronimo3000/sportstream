from autodownloader import *
from pytest import fixture

@fixture
def team() -> str:
    return "vikings"

@fixture
def site():
    return Sportsurge()

def test_get_all_possible_urls(site,team):
    game_urls = site.get_current_game_url_all(team)
    print('\n'.join(game_urls))
    assert len(game_urls) > 1
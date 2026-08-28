from autodownloader import Sportsurge

def test_base_url_from_team_NFL():
    site = Sportsurge()
    assert site.get_base_url(team_name="vikings") == "https://v2.sportsurge.net/watch-nfl-streams/"

def test_base_url_from_team_NBA():
    site = Sportsurge()
    assert site.get_base_url(team_name="thunder") == "https://v2.sportsurge.net/watch-basketball-streams/"

def test_get_game_url_team_NFL():
    site = Sportsurge()
    url = site.get_current_game_url(team_name="commanders")
    print(f"This is the URL: {url}")
    assert url is not None

test_get_game_url_team_NFL()
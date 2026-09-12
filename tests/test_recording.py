from pytest import fixture
from autodownloader import *
from datetime import datetime
from pathlib import Path

@fixture
def schedule():
    return {
        "baseball": {
            "channels": {
                "1": {
                    "games": [
                        {
                            "team_1": "dodgers",
                            "team_2": "reds",
                            "time_start": "2026-09-14T22:40:00+00:00",
                            "time_end": "2026-09-15T01:40:00+00:00"
                        }
                    ]
                }
            }
        }
    }

@fixture
def team_data():
    return {
        "dodgers": {
            "sport": "baseball",
            "league": "MLB"
        },
        "reds": {
            "sport": "baseball",
            "league": "MLB"
        }
    }

@fixture
def recorder(game):
    return Recording_writer(game)

@fixture
def game():
    return Game(
        sport="baseball",
        league="MLB",
        team_1="dodgers",
        team_2="reds",
        time_start=datetime.fromisoformat("2026-09-14T22:40:00+00:00"),
        time_end=datetime.fromisoformat("2026-09-15T01:40:00+00:00")
    )

def test_sport_recording_directory(recorder,game):
    print(recorder.game.time_start)
    assert recorder.recording_end_filepath() == "MLB baseball/Season 2026/MLB baseball - S2026E0914 - dodgers @ reds.ts"
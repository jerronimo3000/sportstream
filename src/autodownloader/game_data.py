from dataclasses import dataclass
from datetime import datetime
from .constants import Constants
import json
from functools import cached_property

def get_schedule() -> dict:
    with open(Constants.schedule_file, "r") as f:
        data = json.load(f)
    return data

def get_team_data() -> dict:
    with open(Constants.team_data, "r") as f:
        data = json.load(f)
    return data

def get_sport_data() -> dict:
    with open(Constants.sport_data, "r") as f:
        data = json.load(f)
    return data

@dataclass
class Team:
    name: str
    sport: str
    league: str

@dataclass
class Game:
    sport: str
    league: str
    team_1: str
    team_2: str
    time_start: datetime
    time_end: datetime
    id: str
    game_page_url: str = ""

SCHEDULE = get_schedule()
class Game_data_manager:
    def __init__(self,sport: str, channel: int, search_time: datetime | None = None):
        self.sport = sport
        self.channel = str(channel)
        self.search_time = search_time if search_time is not None else datetime.now(timezone.utc)
        print(self.search_time)
    
    @property
    def schedule(self):
        return SCHEDULE
    
    @cached_property
    def team_data(self):
        return get_team_data()

    def get_cached_game_url(self) -> str:
        return self.active_game.game_page_url
    
    def write_m3u8_info(self,game_page_url: str):
        self.schedule[self.sport]["channels"][self.channel]["games"][self.active_game_index]["game_page_url"] = game_page_url

        with open(Constants.schedule_file, "w") as f:
            json.dump(self.schedule, f, indent=4)

    @cached_property
    def active_game_index(self) -> int:
        games = self.find_possible_games()
        for i,game in enumerate(games):
            if self.game_is_on_now(game):
                return i
       
    @cached_property
    def active_game(self) -> Game:
        print(f"finding team playing {self.sport} on channel {self.channel}")
        games = self.find_possible_games()
        for game in games:
            if self.game_is_on_now(game):
                league = self.team_data[game["team_1"]]["league"]
                active_game = Game(sport=self.sport,league=league,**game)
        try:
            return active_game
        except Exception as e:
            print("No active game")
            return None

    @cached_property
    def currently_playing_team(self) -> str:
        game = self.active_game
        if game is None:
            return None
        return game.team_1

    def game_is_on_now(self,game: dict) -> bool:
        time_start = datetime.fromisoformat(game["time_start"])
        time_end = datetime.fromisoformat(game["time_end"])

        return time_start <= self.search_time and time_end >= self.search_time

    def find_possible_games(self):
        games = self.schedule[self.sport]["channels"][self.channel]["games"]
        return games
    
    @property
    def nearest_game(self):
        games = self.find_possible_games()
        nearest_game = self.sort_games_by_proximity(games)[0]
        league = self.team_data[nearest_game["team_1"]]["league"]
        nearest_game = Game(sport=self.sport,league=league,**nearest_game)
        return nearest_game

    def sort_games_by_proximity(self,games: list[dict]) -> list[dict]:
        time_diff = self.get_time_difference(games)
        sorted_games = [sorted_zipped[0] for sorted_zipped in sorted(zip(games,time_diff),key=lambda x: x[1])]
        return sorted_games

    def get_time_difference(self,games: list[dict]) -> list[float]:
        time_diff = []
        for game in games:
            time_diff_start = abs(self.search_time - datetime.fromisoformat(game["time_start"]))
            time_diff_end = abs(self.search_time - datetime.fromisoformat(game["time_end"]))
            time_diff_min = min(time_diff_start,time_diff_end)
            time_diff.append(time_diff_min)
        return time_diff




def convert_to_str_with_leading_zeroes(num: int,output_digits: int) -> str:
    num_str = str(num)
    if len(num_str) >= output_digits:
        formatted_num = num_str
    else:
        leading_zeroes = ["0"]*(output_digits - len(num_str))
        formatted_num = "".join([*leading_zeroes,num_str])
    return formatted_num

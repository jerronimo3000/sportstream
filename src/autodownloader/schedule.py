import icalendar as ical
from icalendar import Calendar, Component
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import ClassVar
import json
from datetime import datetime
import pytz

class Schedule_generator_from_calendar(ABC):
    @abstractmethod
    def generate_schedule_from_calendar(self):
        pass

    @cached_property
    def sport_data(self):
        with open(Path(__file__).resolve().parent / "data/sport_data.json") as f:
            data = json.load(f)
        return data

    def get_time_start_from_component(self,component: Component) -> datetime:
        time_start_ical = component.get("dtstart").dt.isoformat()
        return time_start_ical
    def get_time_end_from_component(self,component: Component) -> datetime:
        time_end_ical = component.get("dtend").dt.isoformat()
        return time_end_ical

class Schedule_generator_from_calendar_MLB(Schedule_generator_from_calendar):
    sport: ClassVar[str] = "baseball"
    league: ClassVar[str] = "MLB"
    
    def __init__(self,calendar_file: Path | str = Path(__file__).resolve().parent / "data/MLB_cal.ics"):
        self.calendar_file = calendar_file

    @cached_property
    def calendar(self):
        with open(self.calendar_file,"rb") as cal:
            return Calendar.from_ical(cal.read())

    def generate_schedule_from_calendar(self):
        schedule = Schedule()
        for component in self.calendar.walk():
            if is_event(component):
                game = self.create_game_from_calendar_event(component)
                schedule.add_game(game)
        return schedule

    def create_game_from_calendar_event(self,component: Component) -> dict:
        game = {}
        teams = self.get_teams_from_calendar_string(component["SUMMARY"])
        game["team_1"] = teams[0]
        game["team_2"] = teams[1]
        game["time_start"] = self.get_time_start_from_component(component)
        game["time_end"] = self.get_time_end_from_component(component)
        return game

    def get_teams_from_calendar_string(self,summary: str) -> list[str]:
        teams = summary.split(" @ ")
        standardized_teams = [self.get_standardized_team(team) for team in teams]
        # if not all(team is None for team in standardized_teams):
        #     print(standardized_teams)
        return standardized_teams

    def get_standardized_team(self,team: str) -> str:
        all_teams = self.sport_data["sports"][self.sport]["leagues"][self.league]["teams"]
        for standard_team in all_teams:
            if standard_team in team.lower():
                return standard_team



class Schedule_generator_from_calendar_NBA(Schedule_generator_from_calendar):
    sport: ClassVar[str] = "basketball"
    league: ClassVar[str] = "NBA"
    
    def __init__(self,calendar_file: Path | str = Path(__file__).resolve().parent / "data/NBA_cal.ics"):
        self.calendar_file = calendar_file

    @cached_property
    def calendar(self):
        with open(self.calendar_file,"rb") as cal:
            return Calendar.from_ical(cal.read())

    def generate_schedule_from_calendar(self):
        schedule = Schedule()
        for component in self.calendar.walk():
            if is_event(component):
                game = self.create_game_from_calendar_event(component)
                schedule.add_game(game)
        return schedule

    def create_game_from_calendar_event(self,component: Component) -> dict:
        game = {}
        teams = self.get_teams_from_calendar_string(component["SUMMARY"])
        game["team_1"] = teams[0]
        game["team_2"] = teams[1]
        game["time_start"] = self.get_time_start_from_component(component)
        game["time_end"] = self.get_time_end_from_component(component)
        return game

    def get_teams_from_calendar_string(self,summary: str) -> list[str]:
        teams = summary.split(" @ ")
        standardized_teams = [self.get_standardized_team(team) for team in teams]
        # if not all(team is None for team in standardized_teams):
        #     print(standardized_teams)
        return standardized_teams

    def get_standardized_team(self,team: str) -> str:
        all_teams = self.sport_data["sports"][self.sport]["leagues"][self.league]["teams"]
        for standard_team in all_teams:
            if standard_team in team.lower():
                return standard_team
    
class Schedule:
    def __init__(self):
        self.schedule = {}

    def add_game(self,game: dict):
        date = str(datetime.fromisoformat(game["time_start"]).date())

        if not date in self.schedule:
            self._initiate_date(game,date)
        else:
            open_channel = self.get_first_open_channel(game)
            self._add_game_to_channel(game,open_channel)
    
    def _initiate_date(self,game: dict, date: str):
        self.schedule[date] = {"channels": {1: {"games": [game]}}}

    def get_first_open_channel(self,game: dict) -> int:
        date = str(datetime.fromisoformat(game["time_start"]).date())
        existing_free_channel = False
        for channel in self.schedule[date]["channels"]:
            if not self._interferes_with_existing_game_on_channel(game,channel):
                existing_free_channel = channel
                break
        if existing_free_channel:
            open_channel = existing_free_channel
        else:
            open_channel = max(self.schedule[date]["channels"]) + 1
        return open_channel

    def _interferes_with_existing_game_on_channel(self,game: dict, channel: int) -> bool:
        date = str(datetime.fromisoformat(game["time_start"]).date())
        existing_games = self.schedule[date]["channels"][channel]["games"]

        interferes = False
        for existing_game in existing_games:
            game_start_time = datetime.fromisoformat(game["time_start"])
            existing_game_start_time = datetime.fromisoformat(existing_game["time_start"])
            existing_game_end_time = datetime.fromisoformat(existing_game["time_end"])
            if (game_start_time >= existing_game_start_time) and (game_start_time <= existing_game_end_time):
                interferes = True
        
        return interferes
    
    def _add_game_to_channel(self,game: dict, channel: id):
        date = str(datetime.fromisoformat(game["time_start"]).date())
        if channel in self.schedule[date]["channels"]:
            self.schedule[date]["channels"][channel]["games"].append(game)
        else:
            self.schedule[date]["channels"][channel] = {"games": [game]}

            
        
def is_event(cal_component: Component) -> bool:
    return cal_component.name == "VEVENT" and " @ " in cal_component.get("SUMMARY")

scheduler = Schedule_generator_from_calendar_MLB()
schedule = scheduler.generate_schedule_from_calendar().schedule

print(schedule[list(schedule)[0]])
with open(Path(__file__).resolve().parent / "data/schedule.json","w") as f:
    json.dump(schedule,f,indent=4)
#for date in schedule:
    #print(len(schedule[date]["channels"]))
    # if len(schedule[date]["channels"]) == 2:
    #     print(f"Channel 1: {schedule[date]["channels"][1]}")
    #     print(f"Channel 2: {schedule[date]["channels"][2]}")
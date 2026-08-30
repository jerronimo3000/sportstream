import icalendar as ical
from icalendar import Calendar, Component
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import ClassVar
import json

class Schedule_generator_from_calendar(ABC):
    @abstractmethod
    def generate_schedule_from_calendar(self):
        pass

    @cached_property
    def sport_data(self):
        with open(Path(__file__).resolve().parent / "data/sport_data.json") as f:
            data = json.load(f)
        return data

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
        schedule = {}
        for component in self.calendar.walk():
            if is_event(component):
                game = self.create_game_from_calendar_event(component)

    def create_game_from_calendar_event(self,component: Component) -> dict:
        teams = self.get_teams_from_calendar_string(component["SUMMARY"])
    def get_teams_from_calendar_string(self,summary: str) -> list[str]:
        teams = summary.split(" @ ")
        standardized_teams = [self.get_standardized_team(team) for team in teams]
        if not all(team is None for team in standardized_teams):
            print(standardized_teams)
        return standardized_teams

    def get_standardized_team(self,team: str) -> str:
        all_teams = self.sport_data["sports"][self.sport]["leagues"][self.league]["teams"]
        for standard_team in all_teams:
            if standard_team in team.lower():
                return standard_team
            
def is_event(cal_component: Component) -> bool:
    return cal_component.name == "VEVENT"

scheduler = Schedule_generator_from_calendar_MLB()
print(scheduler.generate_schedule_from_calendar())
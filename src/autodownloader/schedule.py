import icalendar as ical
from icalendar import Calendar, Component
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import ClassVar
import json
from datetime import datetime,timezone
import pytz
import xmltv
import xml.etree.ElementTree as ET
from xml.dom import minidom
import copy

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
        dt = component.get("dtstart").dt
        dt_utc = self.enforce_utc_timezone_info(dt)
        time_start_ical = dt_utc.isoformat()
        return time_start_ical
    def get_time_end_from_component(self,component: Component) -> datetime:
        dt = component.get("dtend").dt
        dt_utc = self.enforce_utc_timezone_info(dt)
        time_end_ical = dt_utc.isoformat()
        return time_end_ical
    
    def enforce_utc_timezone_info(self,dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt_utc = dt.replace(tzinfo=timezone.utc)
        else:
            dt_utc = dt.astimezone(timezone.utc)

        return dt_utc


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
        return {self.sport: schedule.schedule}

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
        return {self.sport: schedule.schedule}

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
        self.schedule = {"channels": {1: {"games": []}}}

    def add_game(self,game: dict):
        open_channel = self.get_first_open_channel(game)
        self._add_game_to_channel(game,open_channel)
    
    def _initiate_date(self,game: dict, date: str):
        self.schedule[date] = {"channels": {1: {"games": [game]}}}

    def get_first_open_channel(self,game: dict) -> int:
        existing_free_channel = False
        for channel in self.schedule["channels"]:
            if not self._interferes_with_existing_game_on_channel(game,channel):
                existing_free_channel = channel
                break
        if existing_free_channel:
            open_channel = existing_free_channel
        else:
            open_channel = max(self.schedule["channels"]) + 1
        return open_channel

    def _interferes_with_existing_game_on_channel(self,game: dict, channel: int) -> bool:
        existing_games = self.schedule["channels"][channel]["games"]

        interferes = False
        for existing_game in existing_games:
            game_start_time = datetime.fromisoformat(game["time_start"])
            game_end_time = datetime.fromisoformat(game["time_end"])
            existing_game_start_time = datetime.fromisoformat(existing_game["time_start"])
            existing_game_end_time = datetime.fromisoformat(existing_game["time_end"])
            if (game_start_time >= existing_game_start_time) and (game_start_time <= existing_game_end_time):
                interferes = True
            if (game_end_time >= existing_game_start_time) and (game_end_time <= existing_game_end_time):
                interferes = True
            if (existing_game_start_time >= game_start_time) and (existing_game_end_time <= game_end_time):
                interferes = True
        
        return interferes
    
    def _add_game_to_channel(self,game: dict, channel: id):
        if channel in self.schedule["channels"]:
            self.schedule["channels"][channel]["games"].append(game)
        else:
            self.schedule["channels"][channel] = {"games": [game]}

    def get_epg_xml(self):
        pass
        

class Epg_xml_generator:
    def __init__(self,schedule: dict):
        self.schedule = schedule
        self.tv: ET.Element | None = None
        
    
    def generate_epg_xml(self):
        self.initialize_base_element()
        self.write_channels()
        self.write_programs()
        self.write_to_disk()

    def initialize_base_element(self):
        self.tv = ET.Element(
            "tv",
            {
                "generator-info-name": "The Ocean",
                "generator-info-url": "A boat on the Ocean"
            }
        )

    def write_channels(self):
        channels_per_sport = {sport: self.get_max_number_of_channels(sport) for sport in self.schedule}
        for sport, num_channels in channels_per_sport.items():
            self.write_all_channels_for_sport(sport,num_channels)
    
    def get_max_number_of_channels(self,sport: str) -> int:
        channels_needed_per_day = [len(self.schedule[sport]["channels"]) for date in self.schedule[sport]]
        return max(channels_needed_per_day)
    
    def write_all_channels_for_sport(self,sport,num_channels):
        for i in range(1,num_channels+1):
            self.write_single_channel(sport,i)

    def write_single_channel(self,sport,channel_num):
        name = f"{sport}_{channel_num}"
        channel = ET.SubElement(self.tv, "channel",id=name)
        display_name = ET.SubElement(channel,"display-name")
        display_name.text = f"{sport} {channel_num}"
    
    def write_to_disk(self):
        raw_xml_bytes = ET.tostring(self.tv, encoding="utf-8")
        reparsed = minidom.parseString(raw_xml_bytes)
        pretty_xml = reparsed.toprettyxml(indent="    ")
        with open(Path(__file__).resolve().parent / "data/epg.xml","w") as f:
            f.write(pretty_xml)

    def write_programs(self):
        for sport in self.schedule:
            for channel in self.schedule[sport]["channels"]:
                for game in self.schedule[sport]["channels"][channel]["games"]:
                    full_game_info = copy.copy(game)
                    full_game_info["sport"] = sport
                    full_game_info["channel"] = channel
                    self.write_single_program(full_game_info)
    
    def write_single_program(self,game_info: dict):
        program = ET.SubElement(
            self.tv,
            "programme",
            start=datetime.fromisoformat(game_info["time_start"]).strftime("%Y%m%d%H%M%S %z"),
            stop=datetime.fromisoformat(game_info["time_end"]).strftime("%Y%m%d%H%M%S %z"),
            channel=f"{game_info["sport"]}_{game_info["channel"]}"
        )

        title = ET.SubElement(program, "title", lang="en")
        title.text = f"{game_info["team_1"]} @ {game_info["team_2"]}"

        
def is_event(cal_component: Component) -> bool:
    return cal_component.name == "VEVENT" and " @ " in cal_component.get("SUMMARY")

scheduler = Schedule_generator_from_calendar_MLB()
schedule = scheduler.generate_schedule_from_calendar()

epg_creator = Epg_xml_generator(schedule)
epg_creator.generate_epg_xml()

#print(schedule[list(schedule)[0]])
with open(Path(__file__).resolve().parent / "data/schedule.json","w") as f:
    json.dump(schedule,f,indent=4)
#for date in schedule:
    #print(len(schedule[date]["channels"]))
    # if len(schedule[date]["channels"]) == 2:
    #     print(f"Channel 1: {schedule[date]["channels"][1]}")
    #     print(f"Channel 2: {schedule[date]["channels"][2]}")
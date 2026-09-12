from dataclasses import dataclass
from pathlib import Path
from enum import Enum

class Constants(str,Enum):
    _ignore_ = "relative_path"
    relative_path = Path(__file__).resolve().parent / "data"
    
    schedule_file = relative_path / "schedule.json"
    team_data = relative_path / "team_data.json"
    sport_data = relative_path / "sport_data.json"
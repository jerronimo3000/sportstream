from dataclasses import dataclass
from pathlib import Path
from enum import Enum

class Constants(str,Enum):
    _ignore_ = "relative_path"
    relative_path = Path(__file__).resolve().parent / "data"
    
    schedule_file = relative_path / "schedule.json"
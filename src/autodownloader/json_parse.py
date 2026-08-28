import json
from pathlib import Path
from jsonpath_ng.ext import parse
from functools import cached_property
from abc import ABC

class Team_data_creator:
    
    def open_json_file(self,filepath: str | Path):
        with open(filepath,"r") as f:
            data = json.load(f)
            return data

    def get_team_trees(self,json_data):
        expr = parse("$.sports.*.leagues.*.teams[*]")
        matches = expr.find(json_data)
        return matches

    def build_single_team_info(self,team_tree):
        sanitized_str = str(team_tree.full_path).replace("(", "").replace(")","")
        fields = sanitized_str.split(".")
        sport_index = fields.index("sports") + 1
        league_index = fields.index("leagues") + 1

        sport = fields[sport_index]
        league = fields[league_index]
        team = team_tree.value
        team_info = {"sport": sport, "league": league}
        #tree_fields = [str(field) for field in team_tree.full_path]
        return team_info

    def build_team_info_json(self,team_trees):
        team_data = {}
        for team_tree in team_trees:
            team_data[team_tree.value] = self.build_single_team_info(team_tree)
        return team_data

    def write_team_info(self,
        data_filepath: str | Path = Path(__file__).resolve().parent / "data/sport_data.json",
        output_filepath: str | Path = Path(__file__).resolve().parent / "data/team_data.json"
        ) -> str:
        
        data = self.open_json_file(data_filepath)
        team_trees = self.get_team_trees(data)
        team_info = self.build_team_info_json(team_trees)

        with open(output_filepath,"w") as f:
            json.dump(team_info,f,indent=4)

        

team_data_creator = Team_data_creator()
team_data_creator.write_team_info()

    

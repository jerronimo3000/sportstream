import requests
import json
from pathlib import Path

# TheSportsDB Base V1 URL using public test key '3' (or your personal key)
API_KEY = "3"
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

def fetch_nba_season_schedule(season: str = "2025-2026"):
    """
    Fetches the schedule for an entire NBA season.
    TheSportsDB NBA League ID = 4387
    Season format = 'YYYY-YYYY' (e.g., '2025-2026')
    """
    url = f"{BASE_URL}/eventsseason.php"
    
    params = {
        "id": "4387",     # NBA League ID
        "s": season       # Target season string
    }

    print(f"[+] Fetching NBA schedule for {season}...")
    response = requests.get(url, params=params)

    if response.status_code != 200:
        print(f"[!] Request failed with status code: {response.status_code}")
        return []

    data = response.json()
    events = data.get("events", [])

    if not events:
        print("[!] No events found. (Note: Free test key '3' may limit full season results).")
        return []

    print(f"[+] Successfully fetched {len(events)} games.\n")
    return events


def write_season_data_to_json_file(season_data: dict):
    file_path = Path(__file__).resolve().parent / "data/season_data.json"
    with open(file_path,"w") as f:
        json.dump(season_data,f,indent=4)

if __name__ == "__main__":
    # Fetch schedule for the 2025-2026 NBA season
    nba_games = fetch_nba_season_schedule(season="2026-2027")
    write_season_data_to_json_file(nba_games)
    # Display the first 5 games from the schedule
    for game in nba_games[:5]:
        date = game.get("dateEvent")
        time = game.get("strTime")
        home = game.get("strHomeTeam")
        away = game.get("strAwayTeam")
        
        print(f"Date: {date} {time} | {away} @ {home}")
import json
import os
import requests

def calculate_ros_projection(observed_stat: float, prior_stat: float, games_played: int, stabilization_games: float = 20.0) -> float:
    weight_obs = games_played / (games_played + stabilization_games)
    return round((observed_stat * weight_obs) + (prior_stat * (1.0 - weight_obs)), 1)

def fetch_and_project():
    print("Fetching NBA player stats...")

    session = requests.Session()
    
    # 1. Standard headers without brotli ('br') compression to avoid hanging
    headers = {
        'Host': 'stats.nba.com',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': 'https://www.nba.com/stats/players/traditional',
        'Origin': 'https://www.nba.com',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }

    # 2. Warm up session with a GET request to nba.com to collect valid cookies
    print("Initiating handshake with NBA.com...")
    try:
        session.get(
            "https://www.nba.com/stats",
            headers={'User-Agent': headers['User-Agent']},
            timeout=10
        )
    except Exception as e:
        print(f"Handshake warning (continuing anyway): {e}")

    # 3. Target API endpoint with required query params
    api_url = "https://stats.nba.com/stats/leaguedashplayerstats"
    params = {
        'College': '',
        'Conference': '',
        'Country': '',
        'DateFrom': '',
        'DateTo': '',
        'Division': '',
        'DraftPick': '',
        'DraftYear': '',
        'GameScope': '',
        'GameSegment': '',
        'Height': '',
        'LastNGames': '0',
        'LeagueID': '00',
        'Location': '',
        'MeasureType': 'Base',
        'Month': '0',
        'OpponentTeamID': '0',
        'Outcome': '',
        'PORound': '0',
        'PaceAdjust': 'N',
        'PerMode': 'PerGame',
        'Period': '0',
        'PlayerExperience': '',
        'PlayerPosition': '',
        'PlusMinus': 'N',
        'Rank': 'N',
        'Season': '2024-25',
        'SeasonSegment': '',
        'SeasonType': 'Regular Season',
        'ShotClockRange': '',
        'StarterBench': '',
        'TeamID': '0',
        'VsConference': '',
        'VsDivision': '',
        'Weight': ''
    }

    print("Requesting 2024-25 player stats...")
    response = session.get(api_url, headers=headers, params=params, timeout=20)
    
    if response.status_code != 200:
        raise RuntimeError(f"NBA API rejected request with status code {response.status_code}: {response.text[:200]}")

    data = response.json()
    result_set = data['resultSets'][0]
    headers_list = result_set['headers']
    rows = result_set['rowSet']
    
    records = []
    for row in rows:
        player_dict = dict(zip(headers_list, row))
        gp = int(player_dict['GP'])
        min_pg = float(player_dict['MIN'])
        
        # Only process active players who have played minutes
        if gp < 1 or min_pg <= 0:
            continue
            
        pts = float(player_dict['PTS'])
        reb = float(player_dict['REB'])
        ast = float(player_dict['AST'])
        rem_games = max(0, 82 - gp)

        # Adaptive baseline (starter vs bench expected baseline)
        expected_prior_pts = (min_pg / 30.0) * 14.0 * 1.5 if min_pg > 20 else 11.0

        ros_pts = calculate_ros_projection(pts, expected_prior_pts, gp, stabilization_games=20.0)
        ros_reb = calculate_ros_projection(reb, 5.0, gp, stabilization_games=15.0)
        ros_ast = calculate_ros_projection(ast, 3.0, gp, stabilization_games=15.0)

        final_pts_proj = round(((pts * gp) + (ros_pts * rem_games)) / 82, 1)

        records.append({
            "id": int(player_dict['PLAYER_ID']),
            "name": player_dict['PLAYER_NAME'],
            "team": player_dict['TEAM_ABBREVIATION'],
            "current": {
                "gp": gp,
                "min": round(min_pg, 1),
                "pts": round(pts, 1),
                "reb": round(reb, 1),
                "ast": round(ast, 1)
            },
            "ros_forecast": {
                "proj_pts_avg": ros_pts,
                "proj_reb_avg": ros_reb,
                "proj_ast_avg": ros_ast,
                "end_season_pts_avg": final_pts_proj,
                "rem_games": rem_games
            }
        })

    os.makedirs('public/data', exist_ok=True)
    with open('public/data/forecasts.json', 'w') as f:
        json.dump(records, f, indent=2)

    print(f"Success! Exported {len(records)} player records to public/data/forecasts.json")

if __name__ == '__main__':
    fetch_and_project()
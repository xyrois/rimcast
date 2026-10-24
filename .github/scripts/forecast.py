import json
import os
import random
import time
from nba_api.stats.library import http as stats_http
from nba_api.stats.endpoints import leaguedashplayerstats

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
]

def get_headers():
    return {
        'Host': 'stats.nba.com',
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'Sec-Fetch-Site': 'same-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Connection': 'keep-alive',
    }

def calculate_ros_projection(observed_stat: float, prior_stat: float, games_played: int, stabilization_games: float = 25.0) -> float:
    weight_obs = games_played / (games_played + stabilization_games)
    return round((observed_stat * weight_obs) + (prior_stat * (1.0 - weight_obs)), 1)

def fetch_and_project():
    print("Fetching NBA player stats...")
    
    endpoint = None
    # 5 attempts with increasing sleep to bypass data center rate-limiting
    for attempt in range(1, 6):
        try:
            print(f"Attempt {attempt}/5 connecting to stats.nba.com...")
            headers = get_headers()
            stats_http.STATS_HEADERS = headers
            if hasattr(stats_http.NBAStatsHTTP, 'headers'):
                stats_http.NBAStatsHTTP.headers = headers

            endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
                season='2024-25',
                per_mode_detailed='PerGame',
                headers=headers,
                timeout=60
            )
            df = endpoint.get_data_frames()[0]
            if not df.empty:
                print("Data fetched successfully.")
                break
        except Exception as e:
            wait_time = attempt * 5
            print(f"Attempt {attempt} failed: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    if endpoint is None or df.empty:
        # Prevent wiping existing data if NBA blocks the runner
        if os.path.exists('public/data/forecasts.json') and os.path.getsize('public/data/forecasts.json') > 10:
            print("Warning: API blocked. Retaining existing forecasts.json to avoid pipeline crash.")
            return
        raise RuntimeError("Failed to fetch data from stats.nba.com after 5 attempts.")

    active = df[(df['GP'] >= 1) & (df['MIN'] > 0)].copy()

    league_avg_pts = float(active['PTS'].median())
    league_avg_reb = float(active['REB'].median())
    league_avg_ast = float(active['AST'].median())

    records = []
    for _, row in active.iterrows():
        gp = int(row['GP'])
        min_pg = float(row['MIN'])
        pts = float(row['PTS'])
        reb = float(row['REB'])
        ast = float(row['AST'])
        rem_games = max(0, 82 - gp)

        expected_prior_pts = (min_pg / 30.0) * league_avg_pts * 1.6 if min_pg > 20 else league_avg_pts

        ros_pts = calculate_ros_projection(pts, expected_prior_pts, gp, stabilization_games=20.0)
        ros_reb = calculate_ros_projection(reb, league_avg_reb, gp, stabilization_games=15.0)
        ros_ast = calculate_ros_projection(ast, league_avg_ast, gp, stabilization_games=15.0)

        final_pts_proj = round(((pts * gp) + (ros_pts * rem_games)) / 82, 1) if (gp + rem_games) > 0 else pts

        records.append({
            "id": int(row['PLAYER_ID']),
            "name": row['PLAYER_NAME'],
            "team": row['TEAM_ABBREVIATION'],
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

    print(f"Updated forecasts for {len(records)} players.")

if __name__ == '__main__':
    fetch_and_project()
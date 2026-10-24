import json
import os
import time
from nba_api.stats.library import http as stats_http
from nba_api.stats.endpoints import leaguedashplayerstats

# 1. Full browser-fingerprint headers required by Akamai/Cloudflare on stats.nba.com
BROWSER_HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
}

# 2. Force patch nba_api internal session defaults
stats_http.STATS_HEADERS = BROWSER_HEADERS
if hasattr(stats_http.NBAStatsHTTP, 'headers'):
    stats_http.NBAStatsHTTP.headers = BROWSER_HEADERS


def fetch_and_project():
    print("Fetching NBA player stats...")
    
    # 3. Pull data with retries
    endpoint = None
    for attempt in range(1, 4):
        try:
            print(f"Attempt {attempt}/3 connecting to stats.nba.com...")
            endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
                season='2024-25',   # Tip: if 2026-27 is pre-season or has 0 games, start with '2024-25' or '2023-24' to test
                per_mode_detailed='PerGame',
                headers=BROWSER_HEADERS,
                timeout=45
            )
            break
        except Exception as e:
            print(f"Attempt {attempt} timed out. Retrying in 3 seconds...")
            time.sleep(3)

    if not endpoint:
        raise RuntimeError("Failed to fetch data from stats.nba.com after 3 attempts.")

    df = endpoint.get_data_frames()[0]
    
    # Require at least 1 game played and minutes on the floor
    active = df[(df['GP'] >= 1) & (df['MIN'] > 0)].copy()

    records = []
    for _, row in active.iterrows():
        gp = int(row['GP'])
        pts = float(row['PTS'])
        rem_games = max(0, 82 - gp)
        
        # Shrinkage baseline: 60% league average (14.0) + 40% observed
        ros_pts_proj = round((pts * 0.4) + (14.0 * 0.6), 1)

        records.append({
            "id": int(row['PLAYER_ID']),
            "name": row['PLAYER_NAME'],
            "team": row['TEAM_ABBREVIATION'],
            "current": {
                "gp": gp,
                "pts": round(pts, 1),
                "reb": round(float(row['REB']), 1),
                "ast": round(float(row['AST']), 1)
            },
            "ros_forecast": {
                "proj_pts_avg": ros_pts_proj,
                "rem_games": rem_games
            }
        })

    os.makedirs('public/data', exist_ok=True)
    with open('public/data/forecasts.json', 'w') as f:
        json.dump(records, f, indent=2)

    print(f"Success! Exported {len(records)} player records to public/data/forecasts.json")


if __name__ == '__main__':
    fetch_and_project()
import json
import os
import time
from nba_api.stats.library import http as stats_http
from nba_api.stats.endpoints import leaguedashplayerstats

BROWSER_HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
    'Connection': 'keep-alive',
}

stats_http.STATS_HEADERS = BROWSER_HEADERS
if hasattr(stats_http.NBAStatsHTTP, 'headers'):
    stats_http.NBAStatsHTTP.headers = BROWSER_HEADERS


def calculate_ros_projection(observed_stat: float, prior_stat: float, games_played: int, stabilization_games: float = 25.0) -> float:
    """
    Empirical Bayes shrinkage:
    Weight of observed stat = GP / (GP + stabilization_games)
    - At 5 GP: ~17% observed, ~83% prior
    - At 25 GP: 50% observed, 50% prior
    - At 70 GP: ~74% observed, ~26% prior
    """
    weight_obs = games_played / (games_played + stabilization_games)
    return round((observed_stat * weight_obs) + (prior_stat * (1.0 - weight_obs)), 1)


def fetch_and_project():
    print("Fetching NBA player stats...")
    
    endpoint = None
    for attempt in range(1, 4):
        try:
            print(f"Attempt {attempt}/3 connecting to stats.nba.com...")
            endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
                season='2024-25',
                per_mode_detailed='PerGame',
                headers=BROWSER_HEADERS,
                timeout=45
            )
            break
        except Exception:
            time.sleep(3)

    if not endpoint:
        raise RuntimeError("Failed to fetch data from stats.nba.com")

    df = endpoint.get_data_frames()[0]
    active = df[(df['GP'] >= 1) & (df['MIN'] > 0)].copy()

    # Prior baseline based on starter vs bench tiers
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

        # Baseline scales by minutes played (starters prior != bench prior)
        expected_prior_pts = (min_pg / 30.0) * league_avg_pts * 1.6 if min_pg > 20 else league_avg_pts

        ros_pts = calculate_ros_projection(pts, expected_prior_pts, gp, stabilization_games=20.0)
        ros_reb = calculate_ros_projection(reb, league_avg_reb, gp, stabilization_games=15.0)
        ros_ast = calculate_ros_projection(ast, league_avg_ast, gp, stabilization_games=15.0)

        # Full 82-game weighted final finish
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
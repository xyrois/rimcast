import json
import os
import requests

def calculate_ros_projection(observed_stat: float, prior_stat: float, games_played: int, stabilization_games: float = 20.0) -> float:
    weight_obs = games_played / (games_played + stabilization_games)
    return round((observed_stat * weight_obs) + (prior_stat * (1.0 - weight_obs)), 1)

def get_team_mapping():
    """
    Pulls official team rosters from ESPN's open team endpoint to map athlete IDs to team abbreviations.
    """
    print("Loading NBA team rosters for exact team mapping...")
    teams_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
    try:
        res = requests.get(teams_url, timeout=10)
        data = res.json()
        team_map = {}
        for sport in data.get('sports', []):
            for league in sport.get('leagues', []):
                for team_entry in league.get('teams', []):
                    t = team_entry.get('team', {})
                    abbrev = t.get('abbreviation')
                    t_id = str(t.get('id'))
                    team_map[t_id] = abbrev
        return team_map
    except Exception as e:
        print(f"Warning: Could not fetch team map ({e})")
        return {}

def run_pipeline():
    team_abbrev_map = get_team_mapping()

    print("Fetching active NBA statistics from ESPN open API...")
    url = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete"
    params = {
        'region': 'us',
        'lang': 'en',
        'contentorigin': 'espn',
        'isqualified': 'false',
        'page': '1',
        'limit': '500',
        'sort': 'offensive.avgPoints:desc'
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
    }

    res = requests.get(url, headers=headers, params=params, timeout=15)
    if res.status_code != 200:
        raise RuntimeError(f"ESPN returned status {res.status_code}")

    payload = res.json()
    root_categories = payload.get('categories', [])
    athletes_list = payload.get('athletes', [])

    print(f"Discovered {len(athletes_list)} athletes. Parsing live statistics...")

    records = []
    STABILIZATION_GP = 20.0

    for item in athletes_list:
        athlete = item.get('athlete', {})
        name = athlete.get('displayName')
        espn_id = athlete.get('id')
        
        # Resolve real team abbreviation
        team = None
        # 1. Direct team dict
        if 'team' in athlete and isinstance(athlete['team'], dict):
            team = athlete['team'].get('abbreviation')
        # 2. currentTeam dict
        if not team and 'currentTeam' in athlete and isinstance(athlete['currentTeam'], dict):
            team = athlete['currentTeam'].get('abbreviation')
        # 3. Lookup by team ID from reference links
        if not team:
            team_id = athlete.get('teamId') or (athlete.get('team', {}).get('id') if isinstance(athlete.get('team'), dict) else None)
            if team_id and str(team_id) in team_abbrev_map:
                team = team_abbrev_map[str(team_id)]
        # 4. Fallback from $ref URL if available
        if not team and '$ref' in athlete.get('team', {}):
            ref_url = athlete['team']['$ref']
            team_id = ref_url.rstrip('/').split('/')[-1].split('?')[0]
            team = team_abbrev_map.get(team_id)

        team = team or 'FA'

        # Extract stats from categorical schema
        athlete_cats = item.get('categories', [])
        if not athlete_cats:
            continue

        stat_dict = {}
        for cat_idx, a_cat in enumerate(athlete_cats):
            if cat_idx < len(root_categories):
                cat_schema_names = root_categories[cat_idx].get('names', [])
                cat_vals = a_cat.get('values', [])
                for s_name, val in zip(cat_schema_names, cat_vals):
                    stat_dict[s_name] = val

        try:
            gp = int(float(stat_dict.get('gamesPlayed', stat_dict.get('GP', 0))))
            min_pg = float(stat_dict.get('avgMinutes', stat_dict.get('MIN', 0.0)))
            pts = float(stat_dict.get('avgPoints', stat_dict.get('PTS', 0.0)))
            reb = float(stat_dict.get('avgRebounds', stat_dict.get('REB', 0.0)))
            ast = float(stat_dict.get('avgAssists', stat_dict.get('AST', 0.0)))
        except (ValueError, TypeError):
            continue

        if gp < 1 or min_pg <= 0:
            continue

        # Empirical Bayes baseline prior
        prior_pts = (min_pg / 30.0) * 14.0 * 1.35 if min_pg > 22 else 9.5
        prior_reb = (min_pg / 30.0) * 5.0
        prior_ast = (min_pg / 30.0) * 3.2

        w = gp / (gp + STABILIZATION_GP)
        ros_pts = calculate_ros_projection(pts, prior_pts, gp, stabilization_games=20.0)
        ros_reb = calculate_ros_projection(reb, prior_reb, gp, stabilization_games=15.0)
        ros_ast = calculate_ros_projection(ast, prior_ast, gp, stabilization_games=15.0)

        rem_games = max(0, 82 - gp)
        end_pts = round(((pts * gp) + (ros_pts * rem_games)) / 82, 1)

        history = [
            {
                "season": "Prior Baseline",
                "gp": 70,
                "min": round(min_pg, 1),
                "pts": round(prior_pts, 1),
                "reb": round(prior_reb, 1),
                "ast": round(prior_ast, 1)
            },
            {
                "season": "Current Season",
                "gp": gp,
                "min": round(min_pg, 1),
                "pts": round(pts, 1),
                "reb": round(reb, 1),
                "ast": round(ast, 1)
            }
        ]

        records.append({
            "id": int(espn_id),
            "name": name,
            "team": team,
            "current": {
                "gp": gp,
                "min": round(min_pg, 1),
                "pts": round(pts, 1),
                "reb": round(reb, 1),
                "ast": round(ast, 1)
            },
            "history": history,
            "ros_forecast": {
                "proj_pts_avg": ros_pts,
                "proj_reb_avg": ros_reb,
                "proj_ast_avg": ros_ast,
                "end_season_pts_avg": end_pts,
                "rem_games": rem_games
            }
        })

    records.sort(key=lambda x: x['current']['pts'], reverse=True)

    os.makedirs('public/data', exist_ok=True)
    with open('public/data/forecasts.json', 'w') as f:
        json.dump(records, f, indent=2)

    print(f"Success! Populated public/data/forecasts.json with {len(records)} verified players and team assignments.")

if __name__ == '__main__':
    run_pipeline()
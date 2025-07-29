from flask import Flask, render_template, abort
import requests
import yaml
from datetime import datetime
import pytz

app = Flask(__name__)

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

teams_config = config.get("teams", {})

# Cache for team data: {key: (timestamp, data)}
cache = {}
CACHE_EXPIRATION = 60 * 60  # seconds, 1 hour

ESPN_API_BASE = "http://192.168.1.226:8000/api/espn/team"


def fetch_team_data(team_slug, league_slug):
    url = f"{ESPN_API_BASE}/{team_slug}/{league_slug}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


def get_team_data(team_slug, league_slug):
    key = f"{league_slug}:{team_slug}"
    from time import time
    now = time()

    if key in cache:
        ts, data = cache[key]
        if now - ts < CACHE_EXPIRATION:
            return data

    data = fetch_team_data(team_slug, league_slug)
    cache[key] = (now, data)
    return data


@app.route('/test_api')
def test_api():
    try:
        data = fetch_team_data('arsenal', 'eng.1')
        return data
    except Exception as e:
        return str(e), 500


@app.route('/')
def home():
    """ Show today's upcoming events for all teams """

    london_tz = pytz.timezone("Europe/London")
    today = datetime.now(london_tz).date()

    team_events = []

    for team_key, team_info in teams_config.items():
        espn_slug = team_info.get("espn_slug")
        league_slug = team_info.get("league")
        team_name = team_info.get("name", team_key)

        if not espn_slug or not league_slug:
            continue

        try:
            data = get_team_data(espn_slug, league_slug)
            print(f"Fetched data for {team_name}: {data}")  # DEBUG

            team = data.get("team", {})
            logo = team.get("logo")

            events = data.get("events", [])
            for event in events:
                event_date = event.get("date")
                event_time = event.get("time")
                if not event_date or not event_time:
                    continue

                dt_str = f"{event_date} {event_time}"
                time_format = "%Y-%m-%d %H:%M:%S" if len(event_time) == 8 else "%Y-%m-%d %H:%M"
                try:
                    event_dt_utc = datetime.strptime(dt_str, time_format).replace(tzinfo=pytz.utc)
                except Exception:
                    continue

                event_dt_local = event_dt_utc.astimezone(london_tz)

                print(f"Event date: {event_dt_local.date()}, today: {today}")  # DEBUG

                # Temporarily disable today filtering for testing
                # if event_dt_local.date() != today:
                #     continue

                team_events.append({
                    "team": team_name,
                    "home": event.get("homeTeam"),
                    "away": event.get("awayTeam"),
                    "date": event_date,
                    "time": event_dt_local.strftime("%H:%M"),
                    "venue": event.get("venue"),
                    "thumb": logo,
                    "timestamp": event_dt_local,
                })
        except Exception as e:
            print(f"Error fetching data for {team_name}: {e}")

    # Sort events by datetime
    team_events.sort(key=lambda x: x["timestamp"])

    print(f"Total events to show: {len(team_events)}")  # DEBUG

    # If no events found, add sample static event for testing template
    if not team_events:
        team_events = [
            {
                "team": "Sample Team",
                "home": "Sample Home",
                "away": "Sample Away",
                "date": today.strftime("%Y-%m-%d"),
                "time": "20:00",
                "venue": "Sample Venue",
                "thumb": None,
                "timestamp": datetime.now(london_tz),
            }
        ]

    # Build sports dict and sport_logos for template
    sports = {}
    sport_logos = {}
    for league in config.get("leagues", []):
        sport_key = league.get("sport")
        if sport_key and sport_key not in sports:
            sports[sport_key] = {"name": sport_key.capitalize()}
            sport_logos[sport_key] = f"/static/logos/{sport_key}.png"

    return render_template(
        "home.html",
        events=team_events,
        teams=teams_config,
        sports=sports,
        sport_logos=sport_logos,
    )


@app.route('/fixtures/sport/<league_or_sport_slug>')
def sport_fixtures(league_or_sport_slug):
    """ Show upcoming fixtures for all teams in a league or all teams of a sport """

    london_tz = pytz.timezone("Europe/London")
    now_utc = datetime.now(pytz.utc)

    # First try filtering teams by league slug
    league_teams = {k: v for k, v in teams_config.items() if v.get("league") == league_or_sport_slug}

    # If no teams found, try filtering by sport slug
    if not league_teams:
        league_teams = {k: v for k, v in teams_config.items() if v.get("sport") == league_or_sport_slug}

    if not league_teams:
        return f"<h2>No teams found for '{league_or_sport_slug}'</h2>", 404

    fixtures = []

    for team_key, team_info in league_teams.items():
        espn_slug = team_info.get("espn_slug")
        team_name = team_info.get("name", team_key)

        if not espn_slug:
            continue

        try:
            data = get_team_data(espn_slug, team_info.get("league", ""))
            team = data.get("team", {})
            logo = team.get("logo")

            events = data.get("events", [])
            for event in events:
                event_date = event.get("date")
                event_time = event.get("time")
                if not event_date or not event_time:
                    continue

                dt_str = f"{event_date} {event_time}"
                time_format = "%Y-%m-%d %H:%M:%S" if len(event_time) == 8 else "%Y-%m-%d %H:%M"
                try:
                    event_dt_utc = datetime.strptime(dt_str, time_format).replace(tzinfo=pytz.utc)
                except Exception:
                    continue

                if event_dt_utc < now_utc:
                    continue

                event_dt_local = event_dt_utc.astimezone(london_tz)

                fixtures.append({
                    "home": event.get("homeTeam"),
                    "away": event.get("awayTeam"),
                    "date": event_date,
                    "time": event_dt_local.strftime("%H:%M"),
                    "venue": event.get("venue"),
                    "thumb": logo,
                })
        except Exception as e:
            print(f"Error fetching fixtures for {team_name}: {e}")

    fixtures.sort(key=lambda x: (x["date"], x["time"]))

    return render_template(
        "fixtures.html",
        fixtures=fixtures,
        league_slug=league_or_sport_slug,
    )

from flask import render_template
from datetime import datetime
import pytz

import json

@app.route('/fixtures/team/<team_slug>')
def team_fixtures(team_slug):
    team_info = teams_config.get(team_slug)
    if not team_info:
        return f"Team '{team_slug}' not found", 404

    league_slug = team_info.get("league")
    espn_slug = team_info.get("espn_slug")
    if not espn_slug or not league_slug:
        return f"Missing data for team '{team_slug}'", 400

    team_name = team_info.get("name", team_slug)
    london_tz = pytz.timezone("Europe/London")
    now_utc = datetime.now(pytz.utc)

    fixtures = []

    try:
        data = get_team_data(espn_slug, league_slug)
        events = data.get("events", [])
        for event in events:
            event_date_str = event.get("date")
            if not event_date_str:
                continue

            # Parse date to datetime object with timezone awareness
            event_dt_utc = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))

            # Skip past events
            if event_dt_utc < now_utc:
                continue

            event_dt_local = event_dt_utc.astimezone(london_tz)

            competitions = event.get("competitions", [])
            if not competitions:
                continue
            competition = competitions[0]

            venue = competition.get("venue", {}).get("fullName", "TBA")

            # Extract teams
            home_team = None
            away_team = None
            for comp_team in competition.get("competitors", []):
                team_data = comp_team.get("team", {})
                if comp_team.get("homeAway") == "home":
                    home_team = team_data.get("displayName", "TBA")
                elif comp_team.get("homeAway") == "away":
                    away_team = team_data.get("displayName", "TBA")

            # Team logo from the main team data (optional)
            logo = data.get("team", {}).get("logo")

            fixtures.append({
                "home": home_team or "TBA",
                "away": away_team or "TBA",
                "date": event_dt_local.strftime("%Y-%m-%d"),
                "time": event_dt_local.strftime("%H:%M"),
                "venue": venue,
                "thumb": logo,
            })

        fixtures.sort(key=lambda x: (x["date"], x["time"]))

    except Exception as e:
        return f"Error fetching fixtures for {team_name}: {e}", 500

    return render_template(
        "fixtures.html",
        fixtures=fixtures,
        league_slug=f"{team_name} Fixtures",
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

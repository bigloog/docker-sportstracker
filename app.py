from flask import Flask, render_template, jsonify
import requests
import yaml
from datetime import datetime, timezone
import pytz
from collections import defaultdict

app = Flask(__name__)

# Load config from YAML
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

API_KEY = config.get("api_key", "123")
sports = config.get("sports", {})
teams_config = config.get("teams", {})

teams = {k: v['id'] for k, v in teams_config.items()}
team_names = {k: v['name'] for k, v in teams_config.items()}

team_badges = {}
for name, team in teams_config.items():
    team_id = team['id']
    badge_url = None
    try:
        resp = requests.get(f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/lookupteam.php?id={team_id}")
        resp.raise_for_status()
        team_data = resp.json().get("teams") or []
        if team_data:
            badge_url = team_data[0].get("strTeamBadge")
    except Exception as e:
        print(f"Error fetching badge for {name}: {e}")
    team_badges[name.lower()] = badge_url

sport_logos = {}
for sport_key, sport_info in sports.items():
    league_id = sport_info.get("id")
    if not league_id:
        sport_logos[sport_key] = None
        continue
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/lookupleague.php?id={league_id}"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        leagues = data.get("leagues")
        if leagues and len(leagues) > 0:
            league = leagues[0]
            badge_url = league.get("strBadge") or league.get("strLogo")
            sport_logos[sport_key] = badge_url
        else:
            sport_logos[sport_key] = None
    except Exception as e:
        print(f"Error fetching logo for {sport_key}: {e}")
        sport_logos[sport_key] = None

@app.route('/')
def home():
    team_events = []

    for team_key, team_id in teams.items():
        url = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/eventsnext.php?id={team_id}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            events = data.get("events")
            if not events:
                continue
            for event in events:
                event_time_str = event.get("strTimestamp")
                if not event_time_str:
                    continue
                try:
                    event_time_utc = datetime.strptime(event_time_str, "%Y-%m-%dT%H:%M:%S")
                    event_time_gmt = event_time_utc.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("Europe/London"))
                    today_gmt = datetime.now(pytz.timezone("Europe/London")).date()
                    if event_time_gmt.date() != today_gmt:
                        continue
                    thumb = event.get("strThumb") or team_badges.get(team_key.lower())
                    team_events.append({
                        "team": team_names.get(team_key.lower(), team_key.capitalize()),
                        "home": event.get("strHomeTeam"),
                        "away": event.get("strAwayTeam"),
                        "date": event.get("dateEvent"),
                        "time": event_time_gmt.strftime("%H:%M"),
                        "venue": event.get("strVenue"),
                        "thumb": thumb,
                        "timestamp": event_time_gmt
                    })
                except Exception as e:
                    print(f"Error parsing timestamp for {team_key}: {e}")
                    continue
        except Exception as e:
            print(f"Error fetching data for {team_key}: {e}")
            continue

    team_events.sort(key=lambda x: x["timestamp"])

    return render_template("home.html", sports=sports, teams=teams, team_names=team_names, events=team_events, sport_logos=sport_logos)

@app.route('/fixtures/sport/<sport>')
def sport_fixtures(sport):
    sport_key = sport.lower()
    sport_info = sports.get(sport_key)
    if not sport_info:
        return f"<h2>No data available for sport '{sport}'</h2>", 404
    league_id = sport_info.get("id")
    sport_name = sport_info.get("name", sport_key.capitalize())
    current_season = sport_info.get("season", "2025")
    url = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/eventsseason.php?id={league_id}&s={current_season}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return f"<h2>Error fetching sport data: {e}</h2>", 500
    events = data.get('events')
    if not events:
        return f"<h2>No fixtures available for {sport_name}</h2>", 404
    now_utc = datetime.now(timezone.utc)
    fixtures = []
    for event in events:
        event_date = event.get("dateEvent")
        event_time = event.get("strTime")
        if not event_date:
            continue
        try:
            if event_time:
                time_format = "%H:%M:%S" if len(event_time) == 8 else "%H:%M"
                dt = datetime.strptime(f"{event_date} {event_time}", f"%Y-%m-%d {time_format}")
            else:
                dt = datetime.strptime(event_date, "%Y-%m-%d")
            dt = dt.replace(tzinfo=timezone.utc)
        except Exception as e:
            print(f"Skipping invalid event time: {e}")
            continue
        if dt < now_utc:
            continue
        home = event.get('strHomeTeam') or ''
        away = event.get('strAwayTeam') or ''
        home_badge = event.get("strHomeTeamBadge") or team_badges.get(home.lower()) if home else None
        away_badge = event.get("strAwayTeamBadge") or team_badges.get(away.lower()) if away else None
        thumb = event.get("strThumb") or home_badge or away_badge
        fixtures.append({
            'home': home,
            'away': away,
            'date': event_date,
            'time': event_time,
            'venue': event.get('strVenue'),
            'thumb': thumb,
            'home_badge': home_badge,
            'away_badge': away_badge,
            'tv_station': event.get('strTVStation'),
        })
    fixtures.sort(key=lambda x: (x['date'], x['time'] or ''))
    return render_template("fixtures.html", sport=sport_name, fixtures=fixtures)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

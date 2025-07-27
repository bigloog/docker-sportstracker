from flask import Flask, render_template
import requests
import yaml
from datetime import datetime
import pytz

app = Flask(__name__)

# Load config from YAML
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

API_KEY = config.get("api_key", "123")
sports = config.get("sports", {})
teams = config.get("teams", {})

# Preload team badges
team_badges = {}
for name, team_id in teams.items():
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


@app.route('/')
def home():
    team_events = []

    for team_name, team_id in teams.items():
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

                # Parse event time and convert to Europe/London timezone
                try:
                    event_time_utc = datetime.strptime(event_time_str, "%Y-%m-%dT%H:%M:%S")
                    event_time_gmt = event_time_utc.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("Europe/London"))
                    today_gmt = datetime.now(pytz.timezone("Europe/London")).date()

                    if event_time_gmt.date() != today_gmt:
                        continue  # Only today's fixtures on homepage

                    thumb = event.get("strThumb") or team_badges.get(team_name.lower())

                    team_events.append({
                        "team": team_name.capitalize(),
                        "home": event.get("strHomeTeam"),
                        "away": event.get("strAwayTeam"),
                        "date": event.get("dateEvent"),
                        "time": event_time_gmt.strftime("%H:%M"),
                        "venue": event.get("strVenue"),
                        "thumb": thumb,
                        "timestamp": event_time_gmt
                    })
                except Exception as e:
                    print(f"Error parsing timestamp for {team_name}: {e}")
                    continue

        except Exception as e:
            print(f"Error fetching data for {team_name}: {e}")
            continue

    # Sort today's events by time
    team_events.sort(key=lambda x: x["timestamp"])

    return render_template("home.html",
                           sports=sports.keys(),
                           teams=teams.keys(),
                           events=team_events)


@app.route('/fixtures/sport/<sport>')
def sport_fixtures(sport):
    if sport not in sports:
        return f"<h2>No data available for sport '{sport}'</h2>", 404

    league_id = sports[sport]
    url = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/eventsnextleague.php?id={league_id}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return f"<h2>Error fetching sport data: {e}</h2>", 500

    fixtures = []
    for event in data.get('events') or []:
        thumb = event.get("strThumb")
        if not thumb:
            home = event.get("strHomeTeam", "").lower()
            away = event.get("strAwayTeam", "").lower()
            thumb = team_badges.get(home) or team_badges.get(away)

        fixtures.append({
            'home': event.get('strHomeTeam'),
            'away': event.get('strAwayTeam'),
            'date': event.get('dateEvent'),
            'time': event.get('strTime'),
            'venue': event.get('strVenue'),
            'thumb': event.get('strThumb'),
            'home_badge': event.get('strHomeTeamBadge'),
            'away_badge': event.get('strAwayTeamBadge'),
        })

    return render_template("fixtures.html", sport=sport.capitalize(), fixtures=fixtures)


@app.route('/fixtures/team/<team>')
def team_fixtures(team):
    team = team.lower()
    if team not in teams:
        return f"<h2>No data available for team '{team}'</h2>", 404

    team_id = teams[team]
    url = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/eventsnext.php?id={team_id}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return f"<h2>Error fetching team data: {e}</h2>", 500

    fixtures = []
    for event in data.get('events') or []:
        thumb = event.get("strThumb") or team_badges.get(team)
        fixtures.append({
            'home': event.get('strHomeTeam'),
            'away': event.get('strAwayTeam'),
            'date': event.get('dateEvent'),
            'time': event.get('strTime'),
            'venue': event.get('strVenue'),
            'thumb': event.get('strThumb'),
            'home_badge': event.get('strHomeTeamBadge'),
            'away_badge': event.get('strAwayTeamBadge'),
        })

    return render_template("fixtures.html", sport=team.capitalize(), fixtures=fixtures)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

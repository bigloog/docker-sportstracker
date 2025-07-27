from flask import Flask, render_template
import requests
import yaml

app = Flask(__name__)

# Load config.yaml
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

API_KEY = config.get("api_key")
sports = config.get("sports", {})
teams = config.get("teams", {})

@app.route('/')
def home():
    return render_template("home.html", sports=sports.keys(), teams=teams.keys())

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
    except requests.exceptions.RequestException as e:
        return f"<h2>Error fetching sport data: {e}</h2>", 500

    fixtures = []
    for event in data.get('events', []):
        fixtures.append({
            'home': event.get('strHomeTeam'),
            'away': event.get('strAwayTeam'),
            'date': event.get('dateEvent'),
            'time': event.get('strTime'),
            'venue': event.get('strVenue'),
            'thumb': event.get('strThumb'),
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
    except requests.exceptions.RequestException as e:
        return f"<h2>Error fetching team data: {e}</h2>", 500

    fixtures = []
    for event in data.get('events', []):
        fixtures.append({
            'home': event.get('strHomeTeam'),
            'away': event.get('strAwayTeam'),
            'date': event.get('dateEvent'),
            'time': event.get('strTime'),
            'venue': event.get('strVenue'),
            'thumb': event.get('strThumb'),
        })

    return render_template("fixtures.html", sport=team.capitalize(), fixtures=fixtures)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

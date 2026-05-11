"""ESPN scoreboard + news for the five tracked teams.

For each team:
  1. Look at yesterday's scoreboard for a completed game → last_game.
  2. Look at today's scoreboard for a scheduled game → next_game.
  3. If neither, fall back to the league's news feed for a headline.

Status is "recent" (had a game yesterday), "upcoming" (game today, no game yesterday),
or "offseason" (no game in the two-day window — we use a news headline instead).
"""

import json
from datetime import date, datetime, timedelta

import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports"

# (display name, league slug, team id, extra scoreboard params)
TEAMS = [
    ("NY Giants", "football/nfl", "19", {}),
    ("SF Giants", "baseball/mlb", "26", {}),
    ("Chelsea", "soccer/eng.1", "363", {}),
    ("Cal Football", "football/college-football", "25", {"groups": "80"}),
    ("Warriors", "basketball/nba", "9", {}),
]


def _get_json(url: str, params: dict | None = None) -> dict | None:
    try:
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def _find_team_event(scoreboard: dict | None, team_id: str) -> dict | None:
    if not scoreboard:
        return None
    for event in scoreboard.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        for competitor in comp.get("competitors", []):
            if str(competitor.get("team", {}).get("id")) == team_id:
                return event
    return None


def _summarize_completed(event: dict, team_id: str) -> str | None:
    comp = event["competitions"][0]
    if comp.get("status", {}).get("type", {}).get("state") != "post":
        return None

    us = them = None
    for c in comp["competitors"]:
        if str(c["team"]["id"]) == team_id:
            us = c
        else:
            them = c
    if not us or not them:
        return None

    try:
        us_score = int(us.get("score", 0))
        them_score = int(them.get("score", 0))
    except (TypeError, ValueError):
        return None

    result = "W" if us_score > them_score else "L" if us_score < them_score else "T"
    home_away = "vs" if us.get("homeAway") == "home" else "@"
    opp = them.get("team", {}).get("abbreviation") or them.get("team", {}).get("displayName", "?")
    return f"{result} {us_score}-{them_score} {home_away} {opp}"


def _summarize_upcoming(event: dict, team_id: str) -> str | None:
    comp = event["competitions"][0]
    state = comp.get("status", {}).get("type", {}).get("state")
    if state not in ("pre", "in"):
        return None

    us = them = None
    for c in comp["competitors"]:
        if str(c["team"]["id"]) == team_id:
            us = c
        else:
            them = c
    if not us or not them:
        return None

    opp = them.get("team", {}).get("abbreviation") or them.get("team", {}).get("displayName", "?")
    home_away = "vs" if us.get("homeAway") == "home" else "@"
    when = ""
    raw = comp.get("date")
    if raw:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()
            when = f" {dt.strftime('%-I:%M %p')}"
        except ValueError:
            pass
    return f"{home_away} {opp}{when}"


def _fetch_headline(league: str, team_id: str) -> tuple[str | None, str | None]:
    """Return (headline, url) for the first non-paywalled article, or (None, None)."""
    data = _get_json(f"{BASE}/{league}/news", params={"team": team_id})
    if not data:
        return None, None
    for article in data.get("articles") or []:
        if article.get("premium"):
            continue
        url = ((article.get("links") or {}).get("web") or {}).get("href")
        if url and "espnplus" in url:
            continue
        return article.get("headline"), url
    return None, None


def _fetch_team(team: str, league: str, team_id: str, extra: dict) -> dict:
    today = date.today()
    yesterday = today - timedelta(days=1)
    fmt = lambda d: d.strftime("%Y%m%d")  # noqa: E731

    last_game = next_game = headline = headline_url = None
    status = "offseason"

    yesterday_sb = _get_json(
        f"{BASE}/{league}/scoreboard", params={"dates": fmt(yesterday), **extra}
    )
    event = _find_team_event(yesterday_sb, team_id)
    if event:
        last_game = _summarize_completed(event, team_id)
        if last_game:
            status = "recent"

    today_sb = _get_json(f"{BASE}/{league}/scoreboard", params={"dates": fmt(today), **extra})
    event = _find_team_event(today_sb, team_id)
    if event:
        next_game = _summarize_upcoming(event, team_id)
        if next_game and status != "recent":
            status = "upcoming"

    if not last_game and not next_game:
        headline, headline_url = _fetch_headline(league, team_id)
        status = "offseason"

    return {
        "team": team,
        "status": status,
        "last_game": last_game,
        "next_game": next_game,
        "headline": headline,
        "headline_url": headline_url,
    }


def fetch_all_teams() -> list[dict]:
    teams = [_fetch_team(t, l, tid, extra) for (t, l, tid, extra) in TEAMS]
    # Today's game first, then yesterday's result, then offseason.
    teams.sort(key=lambda t: (t.get("next_game") is None, t.get("status") != "recent"))
    return teams


if __name__ == "__main__":
    print(json.dumps(fetch_all_teams(), indent=2))

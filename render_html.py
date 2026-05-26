"""Render the daily ticket as a single self-contained HTML file.

Replaces the prior reportlab PDF output. The HTML is deployed to Vercel
by main.py after this writes site/index.html.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SITE_DIR = PROJECT_DIR / "site"
OUTPUT_PATH = SITE_DIR / "index.html"


def _format_date(now: datetime) -> str:
    return now.strftime("%A · %B %-d, %Y")


def _format_location(geo: dict | None) -> str:
    if not geo:
        return ""
    city = (geo.get("city") or "").strip()
    region = (geo.get("region") or "").strip()
    if city and region:
        return f"{city}, {region}"
    return city or region


def _format_weather(geo: dict | None, weather: dict | None) -> str:
    if not weather:
        return "Weather unavailable."
    loc = _format_location(geo)
    parts = [
        f"{weather['temp_now']}° now, {weather['condition']}",
        f"H {weather['high']}° · L {weather['low']}°",
        f"{weather['pop']}% rain",
    ]
    body = "   ·   ".join(parts)
    return f"{loc}   ·   {body}" if loc else body


def _team_line(team: dict) -> tuple[str, str | None]:
    status = team.get("status")
    if status == "recent":
        last = team.get("last_game") or ""
        nxt = team.get("next_game")
        if nxt:
            return f"{last}  ·  today {nxt}", None
        return last or "—", None
    if status == "upcoming":
        return f"today {team.get('next_game') or '—'}", None
    if status == "offseason":
        headline = team.get("headline")
        return headline or "offseason", team.get("headline_url")
    return "—", None


_CSS = """
:root {
  --paper: #fbf6e7;
  --ink: #1a1a1a;
  --muted: #555;
  --rule: #d9c897;
  --link: #1a4d8c;
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  background: #efe7c8;
  color: var(--ink);
  font-family: Georgia, "Times New Roman", serif;
}
.page {
  max-width: 720px;
  margin: 36px auto;
  padding: 48px 56px 32px;
  background:
    repeating-linear-gradient(
      to bottom,
      transparent 0,
      transparent 27px,
      var(--rule) 27px,
      var(--rule) 28px
    ),
    var(--paper);
  background-position: 0 96px;
  box-shadow: 0 8px 28px rgba(0,0,0,.18);
  line-height: 28px;
  font-size: 16px;
}
h1.title {
  text-align: center;
  font-size: 26px;
  margin: 0 0 4px;
  font-weight: 700;
  letter-spacing: .02em;
}
.subtitle {
  text-align: center;
  font-style: italic;
  color: var(--muted);
  font-size: 13px;
  margin: 0 0 36px;
}
section { margin: 0 0 28px; }
h2 {
  font-size: 16px;
  margin: 0 0 0;
  font-weight: 700;
  letter-spacing: .03em;
}
.weather { margin: 0; }
.unread-summary {
  font-style: italic;
  color: var(--muted);
  margin: 0 0 8px;
}
ul.inbox {
  list-style: none;
  margin: 0;
  padding: 0;
}
ul.inbox li {
  padding-left: 1em;
  text-indent: -1em;
}
ul.inbox li::before { content: "•  "; }
.empty {
  font-style: italic;
  color: var(--muted);
}
.sports-row {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 8px;
  align-items: baseline;
}
.sports-row .team { font-weight: 700; }
.sports-row .game { color: var(--ink); }
.sports-row .game.muted { color: var(--muted); }
.sports-row .game a {
  color: var(--link);
  text-decoration: underline;
}
footer {
  text-align: center;
  font-style: italic;
  color: var(--muted);
  font-size: 12px;
  margin-top: 24px;
}
@media (prefers-color-scheme: dark) {
  html, body { background: #14110a; }
  .page { box-shadow: 0 8px 28px rgba(0,0,0,.6); }
}
"""


def _esc(s: str | None) -> str:
    return html.escape(s or "", quote=True)


def _inbox_html(inbox: dict | list | None) -> str:
    if isinstance(inbox, list):
        unread_summary, emails = "", inbox
    elif isinstance(inbox, dict):
        unread_summary = inbox.get("unread_summary") or ""
        emails = inbox.get("ranked") or []
    else:
        unread_summary, emails = "", []

    parts = ["<h2>Inbox</h2>"]
    if unread_summary:
        parts.append(f'<p class="unread-summary">{_esc(unread_summary)}</p>')
    if not emails:
        parts.append('<p class="empty">Nothing pressing.</p>')
    else:
        parts.append('<ul class="inbox">')
        for item in emails[:5]:
            sender = _esc(item.get("sender_short", "?"))
            summary = _esc(item.get("summary", ""))
            parts.append(f"<li>{sender} — {summary}</li>")
        parts.append("</ul>")
    return "\n".join(parts)


def _sports_html(sports: list[dict] | None) -> str:
    parts = ["<h2>Sports</h2>"]
    if not sports:
        parts.append('<p class="empty">—</p>')
        return "\n".join(parts)
    for team in sports:
        name = _esc(team.get("team", "?"))
        game_text, url = _team_line(team)
        game_esc = _esc(game_text)
        if url:
            game_html = f'<span class="game"><a href="{_esc(url)}" rel="noopener">{game_esc}</a></span>'
        else:
            game_html = f'<span class="game muted">{game_esc}</span>'
        parts.append(
            f'<div class="sports-row"><span class="team">{name}</span>{game_html}</div>'
        )
    return "\n".join(parts)


def render_ticket(
    geo: dict | None,
    weather: dict | None,
    inbox: dict | list | None,
    sports: list[dict] | None,
    output_path: Path = OUTPUT_PATH,
    now: datetime | None = None,
) -> Path:
    now = now or datetime.now()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="1800">
<title>daily-ticket · {_esc(_format_date(now))}</title>
<style>{_CSS}</style>
</head>
<body>
<main class="page">
  <h1 class="title">{_esc(_format_date(now))}</h1>
  <p class="subtitle">your morning brief</p>
  <section><p class="weather">{_esc(_format_weather(geo, weather))}</p></section>
  <section>{_inbox_html(inbox)}</section>
  <section>{_sports_html(sports)}</section>
  <footer>daily-ticket · updated {now.strftime("%H:%M")}</footer>
</main>
</body>
</html>
"""
    output_path.write_text(body, encoding="utf-8")
    return output_path

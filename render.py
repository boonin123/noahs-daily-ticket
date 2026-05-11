"""Render the daily-ticket PNG.

Output: ~/Desktop/daily-ticket.png at 1200x1600, white background, Georgia
serif. Four sections stacked top-to-bottom: header (date), weather, inbox
(up to 5 bullets), sports (one line per team). Missing sections degrade
gracefully — the renderer never raises on missing data.
"""

import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS_W, CANVAS_H = 1200, 1600
MARGIN = 80
BG = "white"
FG = "#1a1a1a"
MUTED = "#666666"

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
FONT_REGULAR = FONT_DIR / "Georgia.ttf"
FONT_BOLD = FONT_DIR / "Georgia Bold.ttf"
FONT_ITALIC = FONT_DIR / "Georgia Italic.ttf"

SIZE_TITLE = 56
SIZE_HEADER = 32
SIZE_BODY = 22
SIZE_FOOTER = 16

OUTPUT_PATH = Path.home() / "Desktop" / "daily-ticket.png"


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _rule(draw: ImageDraw.ImageDraw, y: int) -> None:
    draw.line([(MARGIN, y), (CANVAS_W - MARGIN, y)], fill=MUTED, width=1)


def _text_lines(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Greedy word-wrap to fit within max_width pixels."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if font.getlength(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    max_width: int,
    line_spacing: int = 8,
    fill: str = FG,
) -> int:
    lines = _text_lines(text, font, max_width)
    line_h = font.size + line_spacing
    for i, line in enumerate(lines):
        draw.text((x, y + i * line_h), line, font=font, fill=fill)
    return y + len(lines) * line_h


def _format_date(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return now.strftime("%A · %B %-d, %Y")


def _format_location(geo: dict | None) -> str:
    if not geo:
        return ""
    city = geo.get("city") or ""
    region = geo.get("region") or ""
    if city and region:
        return f"{city}, {region}"
    return city or region


def _format_weather(geo: dict | None, weather: dict | None) -> str:
    if not weather:
        return "Weather unavailable."
    loc = _format_location(geo)
    parts = [
        f"{weather['temp_now']}° now, {weather['condition']}",
        f"H {weather['high']}° / L {weather['low']}°",
        f"{weather['pop']}% rain",
    ]
    body = " · ".join(parts)
    return f"{loc} · {body}" if loc else body


def _format_team_line(team: dict) -> str:
    status = team.get("status")
    if status == "recent":
        last = team.get("last_game") or ""
        nxt = team.get("next_game")
        if nxt:
            return f"{last} · today {nxt}"
        return last or "—"
    if status == "upcoming":
        nxt = team.get("next_game") or "—"
        return f"today {nxt}"
    if status == "offseason":
        headline = team.get("headline")
        return f"offseason · {headline}" if headline else "offseason"
    return "—"


def render_ticket(
    geo: dict | None,
    weather: dict | None,
    emails: list[dict] | None,
    sports: list[dict] | None,
    output_path: Path = OUTPUT_PATH,
    now: datetime | None = None,
) -> Path:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw = ImageDraw.Draw(img)

    body_w = CANVAS_W - 2 * MARGIN

    title_font = _font(FONT_BOLD, SIZE_TITLE)
    header_font = _font(FONT_BOLD, SIZE_HEADER)
    body_font = _font(FONT_REGULAR, SIZE_BODY)
    body_italic = _font(FONT_ITALIC, SIZE_BODY)
    footer_font = _font(FONT_ITALIC, SIZE_FOOTER)

    y = MARGIN

    # Header (centered)
    date_str = _format_date(now)
    date_w = title_font.getlength(date_str)
    draw.text(((CANVAS_W - date_w) / 2, y), date_str, font=title_font, fill=FG)
    y += SIZE_TITLE + 40

    _rule(draw, y)
    y += 40

    # Weather
    weather_text = _format_weather(geo, weather)
    y = _draw_wrapped(draw, weather_text, body_font, MARGIN, y, body_w)
    y += 40

    _rule(draw, y)
    y += 40

    # Inbox
    draw.text((MARGIN, y), "Inbox", font=header_font, fill=FG)
    y += SIZE_HEADER + 16

    if not emails:
        draw.text((MARGIN, y), "Nothing pressing.", font=body_italic, fill=MUTED)
        y += SIZE_BODY + 12
    else:
        for item in emails[:5]:
            sender = item.get("sender_short", "?")
            summary = item.get("summary", "")
            bullet = f"• {sender} — {summary}"
            y = _draw_wrapped(draw, bullet, body_font, MARGIN, y, body_w, line_spacing=6)
            y += 8

    y += 32
    _rule(draw, y)
    y += 40

    # Sports
    draw.text((MARGIN, y), "Sports", font=header_font, fill=FG)
    y += SIZE_HEADER + 16

    if not sports:
        draw.text((MARGIN, y), "—", font=body_italic, fill=MUTED)
        y += SIZE_BODY + 12
    else:
        team_col_x = MARGIN
        game_col_x = MARGIN + 220
        game_col_w = CANVAS_W - MARGIN - game_col_x
        for team in sports:
            name = team.get("team", "?")
            line = _format_team_line(team)
            draw.text((team_col_x, y), name, font=body_font, fill=FG)
            y = _draw_wrapped(
                draw, line, body_font, game_col_x, y, game_col_w, line_spacing=6, fill=MUTED
            )
            y += 6

    # Footer (bottom-anchored)
    footer = "daily-ticket"
    footer_w = footer_font.getlength(footer)
    draw.text(
        ((CANVAS_W - footer_w) / 2, CANVAS_H - MARGIN),
        footer,
        font=footer_font,
        fill=MUTED,
    )

    img.save(output_path, "PNG")
    return output_path


def _mock_data() -> tuple[dict, dict, list[dict], list[dict]]:
    geo = {"city": "Boston", "region": "Massachusetts", "country": "United States"}
    weather = {
        "temp_now": 58,
        "code": 3,
        "condition": "partly cloudy",
        "high": 67,
        "low": 52,
        "pop": 10,
    }
    emails = [
        {
            "sender_short": "Anthropic",
            "summary": "technical screen interview confirmed for Tuesday May 13 at 2pm PT",
        },
        {
            "sender_short": "Sarah Kim",
            "summary": "wants to discuss senior engineer role at Stripe — available Wed or Thu afternoon",
        },
        {
            "sender_short": "LinkedIn",
            "summary": "5 new Staff Engineer roles in Bay Area — OpenAI, Figma, Notion, Linear, Vercel",
        },
        {
            "sender_short": "Mom",
            "summary": "checking if you're coming up this weekend; dad needs to know about groceries",
        },
        {
            "sender_short": "Dave",
            "summary": "asking if you're free next Friday to grab a beer",
        },
    ]
    sports = [
        {
            "team": "SF Giants",
            "status": "recent",
            "last_game": "W 7-6 vs PIT",
            "next_game": "@ LAD 10:10 PM",
        },
        {
            "team": "Warriors",
            "status": "offseason",
            "headline": "Draft, free agency, trade targets for eliminated teams",
        },
        {
            "team": "Chelsea",
            "status": "offseason",
            "headline": "Premier League players out of contract this summer",
        },
        {
            "team": "NY Giants",
            "status": "offseason",
            "headline": "Giants to host Cowboys in Week 1 on Sunday Night Football",
        },
        {
            "team": "Cal Football",
            "status": "offseason",
            "headline": "Ranking the offseason for every Power 4 college football team",
        },
    ]
    return geo, weather, emails, sports


if __name__ == "__main__":
    geo, weather, emails, sports = _mock_data()
    path = render_ticket(geo, weather, emails, sports)
    print(f"Wrote {path}")
    print(json.dumps({"size_bytes": path.stat().st_size}, indent=2))

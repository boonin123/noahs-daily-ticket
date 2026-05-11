"""Render the daily ticket as a wide-ruled journal-page PDF.

Output: ~/Desktop/daily-ticket.pdf at US Letter, with classic wide-ruled
paper styling (cream background, light-blue horizontal rules, red vertical
margin line). Sports headlines are clickable links to the source article.

The PDF is one page. Every text line is snapped to a rule line so the page
reads like a real journal entry. Missing or empty inputs degrade gracefully
— the renderer never raises on None or [].
"""

import json
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

PAGE_W, PAGE_H = letter  # 612, 792 pt

MARGIN = 50
RULE_SPACING = 28
MARGIN_LINE_X = 95
TEXT_X = 110
TEXT_RIGHT = PAGE_W - MARGIN
TEXT_WIDTH = TEXT_RIGHT - TEXT_X
BASELINE_LIFT = 4  # text baseline sits this many pts above each rule line

CREAM = (0.980, 0.969, 0.941)
RULE_BLUE = (0.710, 0.784, 0.847)
MARGIN_RED = (0.776, 0.341, 0.314)
INK = (0.102, 0.102, 0.102)
INK_MUTED = (0.400, 0.400, 0.400)
LINK_BLUE = (0.137, 0.282, 0.494)

FONT_REGULAR = "Georgia"
FONT_BOLD = "Georgia-Bold"
FONT_ITALIC = "Georgia-Italic"

SIZE_TITLE = 30
SIZE_HEADER = 18
SIZE_BODY = 12
SIZE_FOOTER = 9

OUTPUT_PATH = Path.home() / "Desktop" / "daily-ticket.pdf"

_FONTS_REGISTERED = False


def _register_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    font_dir = Path("/System/Library/Fonts/Supplemental")
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(font_dir / "Georgia.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(font_dir / "Georgia Bold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_ITALIC, str(font_dir / "Georgia Italic.ttf")))
    _FONTS_REGISTERED = True


def _wrap(c: rl_canvas.Canvas, text: str, font: str, size: int, max_width: float) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if c.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_background(c: rl_canvas.Canvas, rules_y: list[float]) -> None:
    c.setFillColorRGB(*CREAM)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    c.setStrokeColorRGB(*RULE_BLUE)
    c.setLineWidth(0.5)
    for y in rules_y:
        c.line(MARGIN, y, PAGE_W - MARGIN, y)

    c.setStrokeColorRGB(*MARGIN_RED)
    c.setLineWidth(1.2)
    c.line(MARGIN_LINE_X, MARGIN, MARGIN_LINE_X, PAGE_H - MARGIN - 8)


def _format_date(now: datetime | None = None) -> str:
    now = now or datetime.now()
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
    body = "   ".join(parts)
    return f"{loc}   ·   {body}" if loc else body


def _draw_link(
    c: rl_canvas.Canvas,
    text: str,
    url: str,
    x: float,
    y: float,
    font: str,
    size: int,
) -> None:
    c.setFillColorRGB(*LINK_BLUE)
    c.setFont(font, size)
    c.drawString(x, y, text)
    text_w = c.stringWidth(text, font, size)
    c.setStrokeColorRGB(*LINK_BLUE)
    c.setLineWidth(0.4)
    c.line(x, y - 1.8, x + text_w, y - 1.8)
    c.linkURL(
        url,
        (x, y - 3, x + text_w, y + size - 2),
        relative=0,
        thickness=0,
    )


def _team_line_parts(team: dict) -> tuple[str, str | None]:
    """Return (game_text, optional_link_url). game_text is plain; the caller
    decides whether to render the offseason headline as a separate link."""
    status = team.get("status")
    if status == "recent":
        last = team.get("last_game") or ""
        nxt = team.get("next_game")
        if nxt:
            return f"{last}  ·  today {nxt}", None
        return last or "—", None
    if status == "upcoming":
        nxt = team.get("next_game") or "—"
        return f"today {nxt}", None
    if status == "offseason":
        headline = team.get("headline")
        url = team.get("headline_url")
        if headline:
            return headline, url
        return "offseason", None
    return "—", None


def render_ticket(
    geo: dict | None,
    weather: dict | None,
    emails: list[dict] | None,
    sports: list[dict] | None,
    output_path: Path = OUTPUT_PATH,
    now: datetime | None = None,
) -> Path:
    _register_fonts()

    c = rl_canvas.Canvas(str(output_path), pagesize=letter)
    c.setTitle("daily-ticket")

    # Pre-compute rule line positions (top to bottom).
    rule_top = 690
    rule_bottom = 60
    rules_y: list[float] = []
    y = rule_top
    while y >= rule_bottom:
        rules_y.append(y)
        y -= RULE_SPACING

    _draw_background(c, rules_y)

    # Title (above the rules)
    c.setFillColorRGB(*INK)
    c.setFont(FONT_BOLD, SIZE_TITLE)
    date_str = _format_date(now)
    title_w = c.stringWidth(date_str, FONT_BOLD, SIZE_TITLE)
    c.drawString((PAGE_W - title_w) / 2, 728, date_str)

    # Small flourish below title
    c.setFillColorRGB(*INK_MUTED)
    c.setFont(FONT_ITALIC, 10)
    sub = "your morning brief"
    sub_w = c.stringWidth(sub, FONT_ITALIC, 10)
    c.drawString((PAGE_W - sub_w) / 2, 711, sub)

    cursor = 0

    def y_at(i: int) -> float:
        return rules_y[i] + BASELINE_LIFT

    def advance(n: int = 1) -> None:
        nonlocal cursor
        cursor += n

    # Weather line
    c.setFillColorRGB(*INK)
    c.setFont(FONT_REGULAR, SIZE_BODY)
    weather_text = _format_weather(geo, weather)
    for line in _wrap(c, weather_text, FONT_REGULAR, SIZE_BODY, TEXT_WIDTH):
        c.drawString(TEXT_X, y_at(cursor), line)
        advance()
    advance()  # blank rule for breathing room

    # Inbox section
    c.setFillColorRGB(*INK)
    c.setFont(FONT_BOLD, SIZE_HEADER)
    c.drawString(TEXT_X, y_at(cursor), "Inbox")
    advance()

    if not emails:
        c.setFillColorRGB(*INK_MUTED)
        c.setFont(FONT_ITALIC, SIZE_BODY)
        c.drawString(TEXT_X, y_at(cursor), "Nothing pressing.")
        advance()
    else:
        c.setFont(FONT_REGULAR, SIZE_BODY)
        for item in emails[:5]:
            if cursor >= len(rules_y):
                break
            sender = item.get("sender_short", "?")
            summary = item.get("summary", "")
            bullet = f"•  {sender} — {summary}"
            wrapped = _wrap(c, bullet, FONT_REGULAR, SIZE_BODY, TEXT_WIDTH)
            for j, line in enumerate(wrapped):
                if cursor >= len(rules_y):
                    break
                indent = 0 if j == 0 else 14
                c.setFillColorRGB(*INK)
                c.drawString(TEXT_X + indent, y_at(cursor), line)
                advance()

    advance()  # blank rule

    # Sports section
    if cursor < len(rules_y):
        c.setFillColorRGB(*INK)
        c.setFont(FONT_BOLD, SIZE_HEADER)
        c.drawString(TEXT_X, y_at(cursor), "Sports")
        advance()

    if not sports:
        if cursor < len(rules_y):
            c.setFillColorRGB(*INK_MUTED)
            c.setFont(FONT_ITALIC, SIZE_BODY)
            c.drawString(TEXT_X, y_at(cursor), "—")
            advance()
    else:
        team_col_w = 100
        game_col_x = TEXT_X + team_col_w + 8
        game_col_w = TEXT_RIGHT - game_col_x
        for team in sports:
            if cursor >= len(rules_y):
                break
            name = team.get("team", "?")
            game_text, url = _team_line_parts(team)

            c.setFillColorRGB(*INK)
            c.setFont(FONT_BOLD, SIZE_BODY)
            c.drawString(TEXT_X, y_at(cursor), name)

            wrapped = _wrap(c, game_text, FONT_REGULAR, SIZE_BODY, game_col_w)
            for j, line in enumerate(wrapped):
                if cursor >= len(rules_y):
                    break
                y_line = y_at(cursor)
                if url and j == 0:
                    _draw_link(c, line, url, game_col_x, y_line, FONT_REGULAR, SIZE_BODY)
                else:
                    c.setFillColorRGB(*INK_MUTED)
                    c.setFont(FONT_REGULAR, SIZE_BODY)
                    c.drawString(game_col_x, y_line, line)
                advance()

    # Footer
    c.setFillColorRGB(*INK_MUTED)
    c.setFont(FONT_ITALIC, SIZE_FOOTER)
    footer = "daily-ticket"
    footer_w = c.stringWidth(footer, FONT_ITALIC, SIZE_FOOTER)
    c.drawString((PAGE_W - footer_w) / 2, 30, footer)

    c.showPage()
    c.save()
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
            "headline": None,
            "headline_url": None,
        },
        {
            "team": "Warriors",
            "status": "offseason",
            "headline": "Draft, free agency, trade targets for eliminated teams",
            "headline_url": "https://www.espn.com/nba/story/_/id/48432907/nba-offseason-2026-draft-free-agency-trade-targets-30-teams",
        },
        {
            "team": "Chelsea",
            "status": "offseason",
            "headline": "Premier League players out of contract this summer",
            "headline_url": "https://www.espn.com/soccer/story/_/id/47480434/premier-league-players-contract-leave-your-team-free-summer",
        },
        {
            "team": "NY Giants",
            "status": "offseason",
            "headline": "Giants to host Cowboys in Week 1 on Sunday Night Football",
            "headline_url": "https://www.espn.com/nfl/story/_/id/48740437/john-harbaugh-giants-host-cowboys-week-1-sunday-night-football",
        },
        {
            "team": "Cal Football",
            "status": "offseason",
            "headline": "Ranking the offseason for every Power 4 college football team",
            "headline_url": "https://www.espn.com/college-football/story/_/id/48627615/ranking-offseason-college-football-power-4-teams-2026",
        },
    ]
    return geo, weather, emails, sports


if __name__ == "__main__":
    geo, weather, emails, sports = _mock_data()
    path = render_ticket(geo, weather, emails, sports)
    print(f"Wrote {path}")
    print(json.dumps({"size_bytes": path.stat().st_size}, indent=2))

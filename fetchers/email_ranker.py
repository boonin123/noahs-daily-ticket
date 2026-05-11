"""Rank the day's emails with Claude Haiku 4.5.

The rubric lives in ranker_rubric.md at the project root. Edit that file to
tune what counts as "important" — no code changes needed.
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

PROJECT_DIR = Path.home() / "Desktop" / "projects" / "daily-ticket"
RUBRIC_PATH = PROJECT_DIR / "ranker_rubric.md"
ENV_PATH = PROJECT_DIR / ".env"

MODEL = "claude-haiku-4-5-20251001"
MAX_RESULTS = 5

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "unread_summary": {"type": "string"},
        "ranked": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sender_short": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["sender_short", "summary"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["unread_summary", "ranked"],
    "additionalProperties": False,
}


def _load_rubric() -> str:
    return RUBRIC_PATH.read_text()


def _shape_for_model(emails: list[dict]) -> list[dict]:
    return [
        {
            "sender": e.get("sender", ""),
            "subject": e.get("subject", ""),
            "snippet": (e.get("snippet") or "")[:400],
            "unread": bool(e.get("unread")),
            "important": bool(e.get("important")),
        }
        for e in emails
    ]


def rank_emails(emails: list[dict]) -> dict:
    """Return {"unread_summary": str, "ranked": list[dict]} — ranked capped at MAX_RESULTS."""
    empty = {"unread_summary": "", "ranked": []}
    if not emails:
        return empty

    load_dotenv(ENV_PATH)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return empty

    try:
        rubric = _load_rubric()
    except OSError:
        return empty

    client = anthropic.Anthropic(api_key=api_key)
    user_payload = json.dumps(_shape_for_model(emails), ensure_ascii=False)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            cache_control={"type": "ephemeral"},
            system=rubric,
            output_config={
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}
            },
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Here are the last 24 hours of email metadata as a JSON array.\n"
                        f"Produce unread_summary (covering all unread emails) and up to "
                        f"{MAX_RESULTS} ranked items per the rubric.\n\n"
                        f"{user_payload}"
                    ),
                }
            ],
        )
    except anthropic.APIError:
        return empty

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text:
        return empty

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return empty

    if not isinstance(parsed, dict):
        return empty

    return {
        "unread_summary": parsed.get("unread_summary", "") or "",
        "ranked": (parsed.get("ranked") or [])[:MAX_RESULTS],
    }


def _test_fixture() -> list[dict]:
    """Synthetic test list covering both kept and skipped categories."""
    return [
        {
            "sender": "Sarah Kim <sarah.kim@stripe.com>",
            "subject": "Quick chat about the senior engineer role?",
            "snippet": "Hi Noah — I came across your profile and wanted to see if you'd be open to a short call about a senior eng opening on the Payments team. Are you free Wed or Thu afternoon?",
            "unread": True,
            "important": True,
        },
        {
            "sender": "Anthropic Recruiting <recruiting@anthropic.com>",
            "subject": "Interview confirmation — Tuesday May 13 at 2pm PT",
            "snippet": "Confirming your technical screen with Anthropic on Tuesday May 13 at 2:00 PM PT. Zoom link: https://anthropic.zoom.us/j/...",
            "unread": True,
            "important": True,
        },
        {
            "sender": "LinkedIn <jobs-noreply@linkedin.com>",
            "subject": "5 new jobs matching your search 'Staff Engineer Bay Area'",
            "snippet": "New jobs at: OpenAI (Member of Technical Staff), Figma (Staff Eng, Infra), Notion, Linear, Vercel...",
            "unread": True,
            "important": False,
        },
        {
            "sender": "Mom <judy.boonin@gmail.com>",
            "subject": "this weekend?",
            "snippet": "hey honey — are you coming up this weekend? dad wants to know if he should pick up extra groceries. let me know!",
            "unread": True,
            "important": False,
        },
        {
            "sender": "Dave <dave.li@gmail.com>",
            "subject": "saw this and thought of you",
            "snippet": "lol https://example.com/cursed-haskell-meme — also are you around next Friday? wanted to grab a beer",
            "unread": True,
            "important": False,
        },
        {
            "sender": "The Athletic Daily <TheAthletic@e1.theathletic.com>",
            "subject": "NBA Draft Lottery winners and losers",
            "snippet": "With proposed reform on the horizon, this could be the last time we say this, but tanking paid off...",
            "unread": True,
            "important": True,
        },
        {
            "sender": "LinkedIn <notifications-noreply@linkedin.com>",
            "subject": "Congratulate Mark on his work anniversary",
            "snippet": "Mark Thompson is celebrating 3 years at Acme Corp.",
            "unread": True,
            "important": False,
        },
        {
            "sender": "Stratechery by Ben Thompson <ben@stratechery.com>",
            "subject": "The Apple Vision Pro Two Years On",
            "snippet": "An update on Apple's spatial computing bet and what's changed since the initial release...",
            "unread": True,
            "important": False,
        },
        {
            "sender": "Generic Recruiter <noreply@blastrecruiting.io>",
            "subject": "Exciting opportunity — Senior Backend Engineer (Remote)",
            "snippet": "Hi! I have an exciting opportunity at a stealth-mode AI company. Are you open to new roles?",
            "unread": True,
            "important": False,
        },
        {
            "sender": "Doordash <no-reply@doordash.com>",
            "subject": "Your order from Sweetgreen is on the way",
            "snippet": "ETA 8 minutes...",
            "unread": False,
            "important": False,
        },
    ]


if __name__ == "__main__":
    result = rank_emails(_test_fixture())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nempty input → {rank_emails([])}")

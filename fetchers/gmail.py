"""Pull the last day's Gmail metadata (sender, subject, snippet, unread/important flags)."""

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
PROJECT_DIR = Path.home() / "Desktop" / "projects" / "daily-ticket"
TOKEN_PATH = PROJECT_DIR / "token.json"


def _service():
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
        else:
            raise RuntimeError("token.json invalid — re-run setup_gmail.py")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _header(headers: list[dict], name: str) -> str:
    name = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name:
            return h.get("value", "")
    return ""


def fetch_recent_emails(max_results: int = 30) -> list[dict]:
    try:
        service = _service()
        listing = (
            service.users()
            .messages()
            .list(userId="me", q="newer_than:1d", maxResults=max_results)
            .execute()
        )
    except (HttpError, RuntimeError, FileNotFoundError):
        return []

    out: list[dict] = []
    for msg in listing.get("messages", []):
        try:
            full = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject"],
                )
                .execute()
            )
        except HttpError:
            continue

        headers = full.get("payload", {}).get("headers", [])
        labels = full.get("labelIds", []) or []
        out.append(
            {
                "sender": _header(headers, "From"),
                "subject": _header(headers, "Subject"),
                "snippet": full.get("snippet", ""),
                "unread": "UNREAD" in labels,
                "important": "IMPORTANT" in labels,
            }
        )
    return out


if __name__ == "__main__":
    print(json.dumps(fetch_recent_emails(), indent=2))

"""Daily-ticket orchestrator.

Loaded by launchd every morning at 8:00 AM. Each fetch is wrapped so a
single failure (no network, ESPN down, OAuth expired) degrades gracefully
to a missing section rather than failing the whole run.
"""

import logging
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

NETWORK_CHECK_URLS = ["https://api.open-meteo.com/", "https://www.google.com/"]
NETWORK_CHECK_TIMEOUT = 5.0


def _has_network() -> bool:
    for url in NETWORK_CHECK_URLS:
        try:
            req = Request(url, method="HEAD")
            with urlopen(req, timeout=NETWORK_CHECK_TIMEOUT) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            continue
    return False

from dotenv import load_dotenv

from fetchers.email_ranker import rank_emails
from fetchers.geo import fetch as fetch_geo
from fetchers.gmail import fetch_recent_emails
from fetchers.sports import fetch_all_teams
from fetchers.weather import fetch as fetch_weather
from render import render_ticket

PROJECT_DIR = Path.home() / "Desktop" / "projects" / "daily-ticket"
LOG_DIR = PROJECT_DIR / "logs"
LOG_PATH = LOG_DIR / "run.log"
STAMP_DIR = LOG_DIR / "stamps"


def _today_stamp() -> Path:
    return STAMP_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.stamp"


def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("daily-ticket")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(LOG_PATH)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)
    return logger


def _safe(logger: logging.Logger, name: str, fn: Callable[..., Any], *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        logger.exception("%s failed: %s", name, e)
        return None


def main() -> int:
    load_dotenv(PROJECT_DIR / ".env")
    logger = _setup_logging()
    STAMP_DIR.mkdir(exist_ok=True)
    stamp = _today_stamp()
    if stamp.exists():
        logger.info("already ran today (%s); skipping", stamp.name)
        return 0
    if not _has_network():
        logger.warning("no network connectivity; aborting without stamp so next retry can pick up")
        return 75
    logger.info("--- starting daily-ticket run ---")

    geo = _safe(logger, "geo", fetch_geo)
    if geo:
        logger.info("geo: %s, %s (%.3f, %.3f)", geo.get("city"), geo.get("region"),
                    geo.get("lat") or 0, geo.get("lon") or 0)
    else:
        logger.warning("geo unavailable")

    weather = None
    if geo and geo.get("lat") is not None and geo.get("lon") is not None:
        weather = _safe(logger, "weather", fetch_weather, geo["lat"], geo["lon"])
    if weather:
        logger.info("weather: %s°, %s", weather.get("temp_now"), weather.get("condition"))
    else:
        logger.warning("weather unavailable")

    sports = _safe(logger, "sports", fetch_all_teams) or []
    logger.info("sports: %d team blocks", len(sports))

    emails_raw = _safe(logger, "gmail", fetch_recent_emails) or []
    logger.info("gmail: %d messages in last 24h", len(emails_raw))

    ranked = _safe(logger, "email_ranker", rank_emails, emails_raw) or {"unread_summary": "", "ranked": []}
    logger.info(
        "ranker: %d highlighted, summary=%r",
        len(ranked.get("ranked", [])),
        (ranked.get("unread_summary") or "")[:80],
    )

    path = _safe(logger, "render", render_ticket, geo, weather, ranked, sports)
    if path:
        logger.info("Wrote %s at %s", path, datetime.now().strftime("%H:%M:%S"))
        try:
            subprocess.run(["open", str(path)], check=False, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning("open failed: %s", e)
        stamp.touch()
        logger.info("--- end run (ok) ---")
        return 0

    logger.error("render returned no path; nothing written")
    logger.info("--- end run (failed) ---")
    return 1


if __name__ == "__main__":
    sys.exit(main())

# daily-ticket

A morning desktop "ticket" — a journal-style PNG written to `~/Desktop/daily-ticket.png` every day at 8:00 AM by `launchd`. It pulls weather (geolocated by IP), the most important Gmail of the last 24 hours (ranked by Claude), and yesterday's results / today's schedule for five sports teams, then renders it all as a clean serif card.

## Why

A personal experiment in replacing a fragmented morning routine (weather app, inbox triage, sports scores across four sites) with one glanceable artifact on the desktop background. The output is a single image — no notifications, no app to open. If it's stale, that itself is the signal that something broke.

## Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Image rendering | Pillow (system Georgia font) |
| Gmail | Google Gmail API (Python client) — `gmail.readonly` only |
| Email ranking | Anthropic Claude Haiku 4.5 with prompt caching |
| Weather | Open-Meteo (no API key) |
| Geolocation | ip-api.com (no API key) |
| Sports | ESPN public scoreboard + news endpoints |
| Scheduler | macOS `launchd` (survives sleep/wake; cron does not) |

## Architecture

```
            ┌────────────┐
            │  launchd   │  fires daily at 08:00
            └─────┬──────┘
                  ▼
            ┌────────────┐
            │  main.py   │  orchestrates, tolerates partial failure
            └─────┬──────┘
                  │
   ┌──────────┬───┴────┬──────────┬──────────┐
   ▼          ▼        ▼          ▼          ▼
  geo     weather   sports     gmail    email_ranker
                                          (Claude)
                  │
                  ▼
            ┌────────────┐
            │  render.py │  Pillow → PNG
            └─────┬──────┘
                  ▼
      ~/Desktop/daily-ticket.png
```

Each fetcher is a standalone module under `fetchers/`, runnable from the CLI for smoke testing. Network failures degrade gracefully — a missing section renders a placeholder rather than crashing the whole run.

## Project layout

```
daily-ticket/
├── fetchers/
│   ├── geo.py            # ip-api.com
│   ├── weather.py        # Open-Meteo
│   ├── sports.py         # ESPN scoreboard + news
│   ├── gmail.py          # Gmail metadata pull
│   └── email_ranker.py   # Claude Haiku 4.5 ranker
├── ranker_rubric.md      # Editable rubric for the email ranker
├── render.py             # Pillow layout — writes ~/Desktop/daily-ticket.png
├── main.py               # orchestrator               (Phase 5)
├── setup_gmail.py        # one-time OAuth bootstrap
├── requirements.txt
├── PLAN.md               # phased implementation plan
└── README.md
```

Secrets (`.env`, `credentials.json`, `token.json`) and generated files (`.venv/`, `logs/`) are gitignored.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Place a Google Cloud OAuth client JSON at credentials.json (Desktop app type,
# gmail.readonly scope). Then bootstrap the token:
.venv/bin/python setup_gmail.py
```

Add `ANTHROPIC_API_KEY=...` to `.env` for the Phase 3 ranker.

## Smoke-test each fetcher

```bash
.venv/bin/python -m fetchers.geo
.venv/bin/python -m fetchers.weather
.venv/bin/python -m fetchers.sports
.venv/bin/python -m fetchers.gmail
```

## Status

| Phase | Description | State |
|---|---|---|
| 0 | API surface documentation | done |
| 1 | Scaffolding + Gmail OAuth | done |
| 1.5 | Git + GitHub remote | done |
| 2 | Data fetchers | done |
| 3 | Claude email ranker | done |
| 4 | Pillow rendering | done |
| 5 | Orchestration + launchd | pending |
| 6 | End-to-end verification | pending |

See [`PLAN.md`](PLAN.md) for the full phased plan, including the verified API surface for each external service.

## Design notes

- **Gmail scope is read-only.** No modify, no send. The OAuth client is a Desktop app with the user as the only test user.
- **Prompt caching** on the email-ranker's system prompt — the rubric is identical every morning, so cache hits drop the per-run cost to roughly $0.001.
- **No retries.** If a fetcher fails, the section is omitted and execution continues. The next morning's run is the retry.
- **Repo is private.** Rendered images contain email senders and subjects.

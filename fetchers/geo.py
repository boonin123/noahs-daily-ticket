"""IP-based geolocation via ip-api.com (free tier, HTTP only)."""

import json

import requests

ENDPOINT = "http://ip-api.com/json/"


def fetch() -> dict | None:
    try:
        r = requests.get(ENDPOINT, timeout=5)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    if data.get("status") != "success":
        return None

    return {
        "lat": data.get("lat"),
        "lon": data.get("lon"),
        "city": data.get("city"),
        "region": data.get("regionName"),
        "country": data.get("country"),
    }


if __name__ == "__main__":
    print(json.dumps(fetch(), indent=2))

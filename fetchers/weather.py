"""Current + daily weather via Open-Meteo (no API key)."""

import json
import logging
import time

import requests

ENDPOINT = "https://api.open-meteo.com/v1/forecast"

logger = logging.getLogger("daily-ticket")


def _condition(code: int) -> str:
    if code == 0:
        return "clear"
    if 1 <= code <= 3:
        return "partly cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67:
        return "rain"
    if 71 <= code <= 86:
        return "snow"
    if 95 <= code <= 99:
        return "thunderstorm"
    return "unknown"


def fetch(lat: float, lon: float) -> dict | None:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
    }
    data = None
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            r = requests.get(ENDPOINT, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            break
        except (requests.RequestException, ValueError) as e:
            last_err = e
            if attempt == 0:
                time.sleep(1.0)
    if data is None:
        logger.warning("weather fetch failed: %s", last_err)
        return None

    try:
        code = data["current"]["weather_code"]
        return {
            "temp_now": round(data["current"]["temperature_2m"]),
            "code": code,
            "condition": _condition(code),
            "high": round(data["daily"]["temperature_2m_max"][0]),
            "low": round(data["daily"]["temperature_2m_min"][0]),
            "pop": data["daily"]["precipitation_probability_max"][0],
        }
    except (KeyError, IndexError, TypeError):
        return None


if __name__ == "__main__":
    from fetchers.geo import fetch as fetch_geo

    geo = fetch_geo() or {"lat": 37.7749, "lon": -122.4194}
    print(json.dumps(fetch(geo["lat"], geo["lon"]), indent=2))

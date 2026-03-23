"""Fetch same-day odds from The Odds API.

Provides:
    fetch_all_sports()       -> list[str]
    fetch_odds_for_sport()   -> list[dict]
    fetch_same_day_odds()    -> list[dict]  (main entry point)
"""

import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.the-odds-api.com/v4/"

MARKET_KEYS = "h2h,spreads,totals"
REGIONS = "eu,uk,us"


def _get_api_key() -> str:
    key = os.getenv("ODDS_API_KEY")
    if not key:
        raise ValueError("ODDS_API_KEY environment variable is not set")
    return key


def fetch_all_sports() -> list[str]:
    """GET /v4/sports/ and return a list of sport keys."""
    key = _get_api_key()
    url = f"{BASE_URL}sports/"
    params = {"apiKey": key, "all": "true"}

    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        raise ValueError(
            f"Failed to fetch sports list: HTTP {resp.status_code} — {resp.text}"
        )

    remaining = resp.headers.get("x-requests-remaining", "unknown")
    print(f"[fetch_odds] API quota remaining after sports list: {remaining}")

    sports = resp.json()
    return [s["key"] for s in sports]


def fetch_odds_for_sport(sport_key: str) -> list[dict]:
    """GET /v4/sports/{sport_key}/odds/ and return the raw list of event dicts."""
    key = _get_api_key()
    url = f"{BASE_URL}sports/{sport_key}/odds/"
    params = {
        "apiKey": key,
        "regions": REGIONS,
        "markets": MARKET_KEYS,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }

    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        raise ValueError(
            f"HTTP {resp.status_code} for sport '{sport_key}' — {resp.text}"
        )

    remaining = resp.headers.get("x-requests-remaining", "unknown")
    print(f"[fetch_odds] API quota remaining after {sport_key}: {remaining}")

    return resp.json()


def fetch_same_day_odds() -> list[dict]:
    """Fetch all same-day events across every active sport.

    Calls fetch_all_sports(), then fetch_odds_for_sport() for each sport.
    Keeps only events whose commence_time falls on today's date (in the user's
    local timezone) and is before 23:59 local time today.

    Returns a flat list of event dicts from The Odds API.
    """
    # Determine today's local date and a local-time cutoff at 23:59
    now_local = datetime.now()
    today_local = now_local.date()
    cutoff_local = now_local.replace(hour=23, minute=59, second=0, microsecond=0)

    # We'll compare by converting the UTC commence_time to local time.
    # Python's datetime.astimezone() uses the system's local timezone.
    try:
        sport_keys = fetch_all_sports()
    except ValueError as exc:
        print(f"[fetch_odds] ERROR fetching sports list: {exc}")
        return []

    all_events: list[dict] = []

    for sport_key in sport_keys:
        try:
            events = fetch_odds_for_sport(sport_key)
        except ValueError as exc:
            print(f"[fetch_odds] WARNING — skipping {sport_key}: {exc}")
            time.sleep(0.1)
            continue

        for event in events:
            commence_raw = event.get("commence_time", "")
            if not commence_raw:
                continue

            # The Odds API returns ISO 8601 UTC strings ending in 'Z'.
            # datetime.fromisoformat() in Python < 3.11 doesn't handle 'Z',
            # so we normalise it to '+00:00'.
            commence_str = commence_raw.replace("Z", "+00:00")
            try:
                # Parse as timezone-aware UTC datetime
                commence_utc = datetime.fromisoformat(commence_str)
                if commence_utc.tzinfo is None:
                    commence_utc = commence_utc.replace(tzinfo=timezone.utc)
            except ValueError:
                print(
                    f"[fetch_odds] WARNING — could not parse commence_time "
                    f"'{commence_raw}' for event {event.get('id')}; skipping."
                )
                continue

            # Convert to local wall-clock time for date/cutoff comparison
            commence_local = commence_utc.astimezone(tz=None).replace(tzinfo=None)

            if commence_local.date() == today_local and commence_local <= cutoff_local:
                all_events.append(event)

        time.sleep(0.1)

    print(
        f"[fetch_odds] Fetched {len(all_events)} same-day events "
        f"across {len(sport_keys)} sports."
    )
    return all_events

"""Fetch same-day odds from The Odds API.

Provides:
    fetch_all_sports()       -> list[str]
    fetch_odds_for_sport()   -> list[dict]
    fetch_same_day_odds()    -> list[dict]  (main entry point)
"""

import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from bot.config import get_api_key

load_dotenv()

BASE_URL = "https://api.the-odds-api.com/v4/"

IDT = ZoneInfo("Asia/Jerusalem")

MARKET_KEYS = "h2h,spreads,totals"
REGIONS = "eu,uk,us"

# Whitelist of high-traffic sports — covers most daily games year-round.
# ~12 requests per morning run instead of 80-120 (saves ~85% of API quota).
# Add/remove sport keys as needed. Unknown keys are skipped gracefully.
SPORTS_WHITELIST = [
    # Soccer — top European leagues (daily Sept–May)
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
    # Basketball
    "basketball_nba",
    "basketball_euroleague",
    # Tennis
    "tennis_atp_single_wimbledon",
    "tennis_wta_single_wimbledon",
    # Baseball
    "baseball_mlb",
    # Ice Hockey
    "icehockey_nhl",
]


def fetch_all_sports() -> list[str]:
    """GET /v4/sports/ and return a list of sport keys."""
    key = get_api_key()
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
    key = get_api_key()
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
    # "today" in Israel time
    now_idt = datetime.now(tz=IDT)
    today_idt = now_idt.date()
    # Cutoff: only include events that start before 21:00 IDT
    # so they can finish by 23:59 IDT (~2-3 hours for most sports)
    cutoff_idt = datetime(today_idt.year, today_idt.month, today_idt.day, 21, 0, 0, tzinfo=IDT)

    sport_keys = SPORTS_WHITELIST
    print(f"[fetch_odds] Fetching odds for {len(sport_keys)} whitelisted sports.")
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

            # Convert to IDT for date/cutoff comparison
            commence_idt = commence_utc.astimezone(IDT)

            if commence_idt.date() == today_idt and commence_idt <= cutoff_idt:
                all_events.append(event)

        time.sleep(0.1)

    print(
        f"[fetch_odds] Fetched {len(all_events)} same-day events "
        f"across {len(sport_keys)} sports."
    )
    return all_events

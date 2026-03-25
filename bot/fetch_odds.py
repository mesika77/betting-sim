"""Fetch same-day odds from odds-api.io.

Provides:
    fetch_same_day_odds() -> list[dict]  (main entry point)
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from bot.config import get_api_key

load_dotenv()

BASE_URL = "https://api.odds-api.io/v3"
BOOKMAKERS = "1xbet,22Bet"

IDT = ZoneInfo("Asia/Jerusalem")

# Sport slugs for odds-api.io.
# Each slug covers all leagues within that sport.
SPORTS_WHITELIST = [
    "football",    # EPL, La Liga, Bundesliga, Serie A, Ligue 1, UCL, UEL, ...
    "basketball",  # NBA, EuroLeague, ...
    "tennis",      # ATP/WTA
    "baseball",    # MLB
    "ice-hockey",  # NHL, AHL, KHL, SHL, Liiga, ...
]

# Hard cap on total odds API calls per morning run.
# Free tier: 100 req/hour. Events list = 5 calls, so max 90 odds calls.
MAX_EVENTS = 90


def _get_events_for_sport(sport_slug: str, date_from: str, date_to: str) -> list[dict]:
    """GET /events for a sport within a UTC date range."""
    key = get_api_key()
    try:
        resp = requests.get(
            f"{BASE_URL}/events",
            params={"apiKey": key, "sport": sport_slug, "from": date_from, "to": date_to},
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"[fetch_odds] WARNING — network error for '{sport_slug}': {exc}")
        return []

    remaining = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code != 200:
        print(
            f"[fetch_odds] WARNING — HTTP {resp.status_code} for events '{sport_slug}': "
            f"{resp.text[:200]}"
        )
        return []

    events = resp.json()
    print(f"[fetch_odds] '{sport_slug}': {len(events)} events | quota remaining: {remaining}")
    return events


def _get_odds_for_event(event_id: int) -> dict | None:
    """GET /odds for a single event. Returns None on error."""
    key = get_api_key()
    try:
        resp = requests.get(
            f"{BASE_URL}/odds",
            params={"apiKey": key, "eventId": event_id, "bookmakers": BOOKMAKERS},
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"[fetch_odds] WARNING — network error for event {event_id}: {exc}")
        return None

    if resp.status_code != 200:
        print(
            f"[fetch_odds] WARNING — HTTP {resp.status_code} for event {event_id}: "
            f"{resp.text[:200]}"
        )
        return None

    return resp.json()


def fetch_same_day_odds() -> list[dict]:
    """Fetch all same-day events with odds across whitelisted sports.

    Filters to events whose commence_time (in IDT) is today and before
    the 21:00 IDT cutoff. Returns a flat list of event dicts enriched
    with a 'bookmakers' key containing odds-api.io bookmaker/market data.
    """
    now_idt = datetime.now(tz=IDT)
    today_idt = now_idt.date()
    cutoff_idt = datetime(today_idt.year, today_idt.month, today_idt.day, 21, 0, 0, tzinfo=IDT)

    date_from = f"{today_idt.isoformat()}T00:00:00Z"
    date_to = f"{today_idt.isoformat()}T23:59:59Z"

    print(f"[fetch_odds] Scanning {len(SPORTS_WHITELIST)} sports for {today_idt} (IDT cutoff: 21:00).")

    # Step 1 — collect qualifying events across all sports
    qualifying: list[dict] = []

    for sport_slug in SPORTS_WHITELIST:
        try:
            events = _get_events_for_sport(sport_slug, date_from, date_to)
        except Exception as exc:
            print(f"[fetch_odds] WARNING — skipping '{sport_slug}': {exc}")
            time.sleep(0.1)
            continue

        for event in events:
            raw_date = event.get("date", "")
            if not raw_date:
                continue
            try:
                commence_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                continue
            commence_idt = commence_utc.astimezone(IDT)
            if commence_idt.date() == today_idt and commence_idt <= cutoff_idt:
                qualifying.append(event)

        time.sleep(0.1)

    print(
        f"[fetch_odds] {len(qualifying)} qualifying events. "
        f"Fetching odds (cap: {MAX_EVENTS})..."
    )
    qualifying = qualifying[:MAX_EVENTS]

    # Step 2 — fetch odds per event
    all_events: list[dict] = []
    for event in qualifying:
        event_id = event.get("id")
        odds_data = _get_odds_for_event(event_id)
        time.sleep(0.1)

        if odds_data is None:
            continue

        bookmakers: dict = odds_data.get("bookmakers", {})
        if not any(len(v) > 0 for v in bookmakers.values()):
            continue  # no odds available for this event

        all_events.append({**event, "bookmakers": bookmakers})

    print(f"[fetch_odds] {len(all_events)} events with odds ready for selection.")
    return all_events

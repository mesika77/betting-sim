"""Fetch same-day odds from odds-api.io.

Provides:
    fetch_same_day_odds() -> list[dict]  (main entry point)
"""

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from bot.config import get_api_key
from bot.espn import ESPN_ENDPOINTS, fetch_scores_for_date, find_score_event

load_dotenv()

BASE_URL = "https://api.odds-api.io/v3"
BOOKMAKERS = "1xbet,22Bet,pinnacle,williamhill,unibet,betway,bwin,marathonbet,betfair"
MULTI_BATCH_SIZE = 10  # /odds/multi supports up to 10 events per call

# Stop fetching odds if quota drops to or below this threshold
QUOTA_RESERVE = 5
# Retry settings for 429 responses
_MAX_RETRIES = 3
_RETRY_BACKOFF = [5, 15, 30]  # fallback if API doesn't send Retry-After header

IDT = ZoneInfo("Asia/Jerusalem")

# Sport slugs for odds-api.io.
# Only sports with ESPN coverage are included.
SPORTS_WHITELIST = [
    "football",    # EPL, La Liga, Bundesliga, Serie A, Ligue 1, UCL, UEL
    "basketball",  # NBA
    "baseball",    # MLB
    "ice-hockey",  # NHL
    # tennis excluded — ESPN has no coverage, all tennis bets void
]


def _api_get(url: str, params: dict, label: str) -> requests.Response | None:
    """GET with retry-on-429 and exponential backoff.

    Returns the Response on success (2xx), None on permanent failure.
    Raises nothing — all errors are logged and swallowed.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)
        except requests.RequestException as exc:
            print(f"[fetch_odds] WARNING — network error ({label}): {exc}")
            return None

        if resp.status_code == 200:
            return resp

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After") or _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)])
            print(f"[fetch_odds] Rate limited ({label}). Waiting {wait}s before retry {attempt + 1}/{_MAX_RETRIES}...")
            time.sleep(wait)
            continue

        print(f"[fetch_odds] WARNING — HTTP {resp.status_code} ({label}): {resp.text[:200]}")
        return None

    print(f"[fetch_odds] WARNING — gave up after {_MAX_RETRIES} retries ({label}).")
    return None


def _remaining_quota(resp: requests.Response) -> int | None:
    """Parse x-requests-remaining header, return None if missing/unparseable."""
    raw = resp.headers.get("x-requests-remaining")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _get_events_for_sport(sport_slug: str, date_from: str, date_to: str) -> list[dict]:
    """GET /events for a sport within a UTC date range."""
    resp = _api_get(
        f"{BASE_URL}/events",
        params={"apiKey": get_api_key(), "sport": sport_slug, "from": date_from, "to": date_to},
        label=f"events/{sport_slug}",
    )
    if resp is None:
        return []

    events = resp.json()
    remaining = _remaining_quota(resp)
    print(f"[fetch_odds] '{sport_slug}': {len(events)} events | quota remaining: {remaining if remaining is not None else '?'}")
    return events


def _get_odds_batch(event_ids: list[int]) -> tuple[list[dict], int | None]:
    """GET /odds/multi for up to 10 events at once.

    Returns (results, quota_remaining). quota_remaining is None if unknown.
    """
    resp = _api_get(
        f"{BASE_URL}/odds/multi",
        params={
            "apiKey": get_api_key(),
            "eventIds": ",".join(str(i) for i in event_ids),
            "bookmakers": BOOKMAKERS,
        },
        label="odds/multi",
    )
    if resp is None:
        return [], None

    data = resp.json()
    remaining = _remaining_quota(resp)
    print(f"[fetch_odds] odds/multi ({len(event_ids)} events) | quota remaining: {remaining if remaining is not None else '?'}")
    return (data if isinstance(data, list) else []), remaining


def fetch_same_day_odds() -> list[dict]:
    """Fetch all same-day events with odds across whitelisted sports.

    Only events that can be found in ESPN's schedule are included — this
    guarantees every bet placed can be resolved in the evening run.

    Uses /odds/multi (10 events per API call) to cover ALL qualifying events
    within the 100 req/hour free tier budget.
    """
    now_idt = datetime.now(tz=IDT)
    today_idt = now_idt.date()
    today_str = today_idt.isoformat()  # "YYYY-MM-DD"
    cutoff_idt = datetime(today_idt.year, today_idt.month, today_idt.day, 21, 0, 0, tzinfo=IDT)

    date_from = f"{today_str}T00:00:00Z"
    date_to = f"{today_str}T23:59:59Z"

    print(f"[fetch_odds] Scanning {len(SPORTS_WHITELIST)} sports for {today_idt} (IDT cutoff: 21:00).")

    # Pre-fetch ESPN schedules for today so we can validate events up-front.
    # This ensures we only bet on games ESPN can resolve in the evening.
    print(f"[fetch_odds] Pre-fetching ESPN schedules for {today_str}...")
    espn_today: dict[str, list[dict]] = {}
    for sport_slug in SPORTS_WHITELIST:
        if ESPN_ENDPOINTS.get(sport_slug):
            espn_today[sport_slug] = fetch_scores_for_date(
                sport_slug, today_str, log_prefix="[fetch_odds]"
            )

    # Step 1 — collect qualifying events across all sports (fetched in parallel)
    def _fetch_sport(sport_slug: str) -> list[dict]:
        try:
            events = _get_events_for_sport(sport_slug, date_from, date_to)
        except Exception as exc:
            print(f"[fetch_odds] WARNING — skipping '{sport_slug}': {exc}")
            return []

        espn_events = espn_today.get(sport_slug, [])
        qualified = []
        for event in events:
            raw_date = event.get("date", "")
            if not raw_date:
                continue
            try:
                commence_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                continue
            commence_idt = commence_utc.astimezone(IDT)
            if not (commence_idt.date() == today_idt and commence_idt <= cutoff_idt):
                continue
            home: str = event.get("home", "")
            away: str = event.get("away", "")
            event_name = f"{home} vs {away}"
            if not find_score_event(event_name, espn_events):
                print(f"[fetch_odds] Skipping '{event_name}' — not in ESPN coverage")
                continue
            qualified.append(event)
        return qualified

    qualifying: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(SPORTS_WHITELIST)) as pool:
        futures = {pool.submit(_fetch_sport, slug): slug for slug in SPORTS_WHITELIST}
        for future in as_completed(futures):
            qualifying.extend(future.result())

    num_batches = math.ceil(len(qualifying) / MULTI_BATCH_SIZE) if qualifying else 0
    print(
        f"[fetch_odds] {len(qualifying)} qualifying events. "
        f"Fetching odds in {num_batches} batches..."
    )

    # Step 2 — fetch odds in batches of 10 via /odds/multi
    event_meta: dict[int, dict] = {e["id"]: e for e in qualifying}
    event_ids = list(event_meta.keys())
    odds_by_id: dict[int, dict] = {}

    for i in range(num_batches):
        batch = event_ids[i * MULTI_BATCH_SIZE:(i + 1) * MULTI_BATCH_SIZE]
        results, quota_remaining = _get_odds_batch(batch)
        for item in results:
            eid = item.get("id")
            if eid is not None:
                odds_by_id[eid] = item.get("bookmakers", {})

        # Stop early if quota is nearly exhausted
        if quota_remaining is not None and quota_remaining <= QUOTA_RESERVE:
            print(
                f"[fetch_odds] WARNING — quota at {quota_remaining}, stopping early "
                f"to preserve reserve of {QUOTA_RESERVE}. "
                f"{num_batches - i - 1} batch(es) skipped."
            )
            break

    # Step 3 — merge odds back, keep only events that have at least some odds
    all_events: list[dict] = []
    for eid, bookmakers in odds_by_id.items():
        if not any(len(v) > 0 for v in bookmakers.values()):
            continue
        event = event_meta.get(eid)
        if event:
            all_events.append({**event, "bookmakers": bookmakers})

    print(f"[fetch_odds] {len(all_events)} events with odds ready for selection.")
    return all_events

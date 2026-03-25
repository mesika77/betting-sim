"""Evening bet resolution script for betting-sim.

Uses the odds-api.io /events endpoint to fetch final scores.

Run every evening at 23:55 IDT by GitHub Actions to:
1. Get all pending bets from the DB
2. Fetch completed event scores from odds-api.io
3. Resolve each bet as won / lost / void
4. Update each bet's result and profit_loss in the DB
5. Write bankroll_history and daily_summary records
6. Print a clear summary to stdout
"""

from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from bot.config import get_api_key
from bot.db import (
    get_pending_bets,
    update_bet_result,
    insert_bankroll_history,
    upsert_daily_summary,
    get_latest_bankroll,
)

load_dotenv()

BASE_URL = "https://api.odds-api.io/v3"
ORIGINAL_BANKROLL = 5000.00

# Map legacy The Odds API sport keys → odds-api.io slugs (for any old unresolved bets)
_LEGACY_TO_SLUG: dict[str, str] = {
    "soccer_epl": "football",
    "soccer_spain_la_liga": "football",
    "soccer_germany_bundesliga": "football",
    "soccer_italy_serie_a": "football",
    "soccer_france_ligue_one": "football",
    "soccer_uefa_champs_league": "football",
    "soccer_uefa_europa_league": "football",
    "basketball_nba": "basketball",
    "basketball_euroleague": "basketball",
    "tennis_atp_single_wimbledon": "tennis",
    "tennis_wta_single_wimbledon": "tennis",
    "baseball_mlb": "baseball",
    "baseball_ncaa": "baseball",
    "icehockey_nhl": "ice-hockey",
    "icehockey_ahl": "ice-hockey",
    "icehockey_khl": "ice-hockey",
    "icehockey_sweden_hockey_league": "ice-hockey",
    "icehockey_finland_liiga": "ice-hockey",
    "icehockey_liiga": "ice-hockey",
    "icehockey_sweden_allsvenskan": "ice-hockey",
}

_NEW_SLUGS = {"football", "basketball", "tennis", "baseball", "ice-hockey"}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _to_sport_slug(sport_value: str) -> str:
    """Convert a DB sport value (old key or new slug) to an odds-api.io slug."""
    if sport_value in _NEW_SLUGS:
        return sport_value
    return _LEGACY_TO_SLUG.get(sport_value, sport_value)


def fetch_scores_for_date(sport_slug: str, date_str: str) -> list[dict]:
    """Fetch all events (with scores) for a sport on a given date (YYYY-MM-DD)."""
    key = get_api_key()
    try:
        resp = requests.get(
            f"{BASE_URL}/events",
            params={
                "apiKey": key,
                "sport": sport_slug,
                "from": f"{date_str}T00:00:00Z",
                "to": f"{date_str}T23:59:59Z",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"[resolve_bets] WARNING — network error for '{sport_slug}': {exc}")
        return []

    remaining = resp.headers.get("x-requests-remaining", "?")
    print(
        f"[resolve_bets] Events fetched for '{sport_slug}' on {date_str} "
        f"| quota remaining: {remaining}"
    )
    if resp.status_code != 200:
        print(f"[resolve_bets] WARNING — HTTP {resp.status_code}: {resp.text[:200]}")
        return []

    return resp.json()


# ---------------------------------------------------------------------------
# Score-matching helpers
# ---------------------------------------------------------------------------

def _normalise(s: str) -> str:
    return s.strip().lower()


def find_score_event(event_name: str, events: list[dict]) -> dict | None:
    """Find the event whose home + away matches 'Home vs Away' event_name."""
    lower = event_name.lower()
    sep = " vs "
    if sep not in lower:
        return None
    idx = lower.index(sep)
    norm_home = _normalise(event_name[:idx])
    norm_away = _normalise(event_name[idx + len(sep):])

    for event in events:
        if (
            _normalise(event.get("home", "")) == norm_home
            and _normalise(event.get("away", "")) == norm_away
        ):
            return event
    return None


def determine_h2h_winner(score_event: dict) -> str | None:
    """Return winning team name, or None on draw / missing scores."""
    scores = score_event.get("scores") or {}
    try:
        h = float(scores["home"])
        a = float(scores["away"])
    except (KeyError, TypeError, ValueError):
        return None

    if h == a:
        return None  # draw
    return score_event["home"] if h > a else score_event["away"]


def determine_totals_result(score_event: dict, selection: str) -> str:
    """Determine won/lost for a totals bet. Selection format: 'Over 5.5'."""
    parts = selection.strip().split()
    if len(parts) != 2:
        return "void"
    direction = parts[0].lower()
    try:
        line = float(parts[1])
    except ValueError:
        return "void"
    if direction not in ("over", "under"):
        return "void"

    scores = score_event.get("scores") or {}
    try:
        total = float(scores["home"]) + float(scores["away"])
    except (KeyError, TypeError, ValueError):
        return "void"

    if direction == "over":
        return "won" if total > line else "lost"
    return "won" if total < line else "lost"


# ---------------------------------------------------------------------------
# Bet resolution
# ---------------------------------------------------------------------------

def resolve_bet(bet: dict, scores_cache: dict) -> tuple[str, float]:
    """Resolve a single bet. scores_cache: {(sport_slug, date_str): [events]}"""
    sport_slug = _to_sport_slug(bet.get("sport", ""))
    event_name = bet.get("event_name", "")
    market = bet.get("market", "").lower()
    selection = bet.get("selection", "")
    decimal_odds = float(bet.get("decimal_odds", 1.0))
    stake = float(bet.get("stake", 0.0))

    bet_date = str(bet.get("date", ""))[:10]
    cache_key = (sport_slug, bet_date)

    if cache_key not in scores_cache:
        scores_cache[cache_key] = fetch_scores_for_date(sport_slug, bet_date)

    events = scores_cache[cache_key]
    score_event = find_score_event(event_name, events)

    if score_event is None:
        print(f"  [VOID] Event not found in scores: '{event_name}' ({sport_slug})")
        return "void", 0.0

    if score_event.get("status") != "finished":
        print(
            f"  [VOID] Event not yet finished "
            f"(status={score_event.get('status', '?')}): '{event_name}'"
        )
        return "void", 0.0

    is_h2h = "match winner" in market or "h2h" in market
    is_totals = "total" in market or "over/under" in market
    is_spreads = "spread" in market or "handicap" in market

    if is_spreads:
        print(f"  [VOID] Spreads market not resolved: '{event_name}'")
        result = "void"

    elif is_h2h:
        winner = determine_h2h_winner(score_event)
        if winner is None:
            print(f"  [LOST] No h2h winner (draw): '{event_name}'")
            result = "lost"
        elif _normalise(selection) == _normalise(winner):
            print(f"  [WON] '{selection}' won: '{event_name}'")
            result = "won"
        else:
            print(f"  [LOST] '{selection}' lost (winner: '{winner}'): '{event_name}'")
            result = "lost"

    elif is_totals:
        result = determine_totals_result(score_event, selection)
        print(f"  [{result.upper()}] Totals '{selection}': '{event_name}'")

    else:
        print(f"  [VOID] Unrecognised market '{market}': '{event_name}'")
        result = "void"

    if result == "won":
        profit_loss = round(stake * (decimal_odds - 1), 2)
    elif result == "lost":
        profit_loss = round(-stake, 2)
    else:
        profit_loss = 0.0

    return result, profit_loss


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Resolve all pending bets and update bankroll records."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"[resolve_bets] Starting evening resolution — {today} UTC")
    print("=" * 60)

    pending_bets = get_pending_bets()
    if not pending_bets:
        print("[resolve_bets] No pending bets found. Nothing to resolve. Exiting cleanly.")
        return

    print(f"[resolve_bets] Found {len(pending_bets)} pending bet(s) to resolve.\n")

    scores_cache: dict = {}
    resolved_bets: list[dict] = []

    for bet in pending_bets:
        bet_id = bet["id"]
        event_name = bet.get("event_name", "?")
        selection = bet.get("selection", "?")
        decimal_odds = float(bet.get("decimal_odds", 1.0))
        stake = float(bet.get("stake", 0.0))

        print(
            f"Resolving: {event_name} | {selection} @ {decimal_odds:.2f} | "
            f"stake=${stake:,.2f}"
        )

        result, profit_loss = resolve_bet(bet, scores_cache)

        try:
            update_bet_result(bet_id, result, profit_loss)
        except Exception as exc:
            print(f"  [ERROR] Failed to update bet {bet_id}: {exc}")
            result = "void"
            profit_loss = 0.0

        resolved_bets.append({**bet, "result": result, "profit_loss": profit_loss})
        print()

    won_bets = [b for b in resolved_bets if b["result"] == "won"]
    lost_bets = [b for b in resolved_bets if b["result"] == "lost"]
    void_bets = [b for b in resolved_bets if b["result"] == "void"]

    daily_pl = sum(b["profit_loss"] for b in resolved_bets)
    opening_balance = get_latest_bankroll()
    closing_balance = round(opening_balance + daily_pl, 2)
    win_rate = len(won_bets) / max(len(won_bets) + len(lost_bets), 1)

    try:
        insert_bankroll_history({
            "date": today,
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "daily_pl": round(daily_pl, 2),
            "total_pl": round(closing_balance - ORIGINAL_BANKROLL, 2),
            "num_bets": len(resolved_bets),
            "num_won": len(won_bets),
            "num_lost": len(lost_bets),
        })
        print("[resolve_bets] bankroll_history record written.")
    except Exception as exc:
        print(f"[resolve_bets] ERROR writing bankroll_history: {exc}")

    try:
        upsert_daily_summary({
            "date": today,
            "bankroll": closing_balance,
            "daily_pl": round(daily_pl, 2),
            "win_rate": round(win_rate, 4),
            "num_bets": len(resolved_bets),
        })
        print("[resolve_bets] daily_summary record written.")
    except Exception as exc:
        print(f"[resolve_bets] ERROR writing daily_summary: {exc}")

    print()
    print("=" * 60)
    print(f"  DAILY RESOLUTION SUMMARY — {today}")
    print("=" * 60)
    print(f"  Bets resolved : {len(resolved_bets)}")
    print(f"  Won           : {len(won_bets)}")
    print(f"  Lost          : {len(lost_bets)}")
    print(f"  Void          : {len(void_bets)}")
    print(f"  Win rate      : {win_rate:.1%}  (excl. voids)")
    print(f"  Daily P&L     : ${daily_pl:+,.2f}")
    print(f"  Opening bal.  : ${opening_balance:,.2f}")
    print(f"  Closing bal.  : ${closing_balance:,.2f}")
    print(f"  Total P&L     : ${closing_balance - ORIGINAL_BANKROLL:+,.2f}")
    print("=" * 60)

    if won_bets:
        print("\n  WINNERS:")
        for b in won_bets:
            print(
                f"    + {b['event_name']} | {b['selection']} "
                f"@ {float(b['decimal_odds']):.2f} | P&L: ${b['profit_loss']:+,.2f}"
            )

    if lost_bets:
        print("\n  LOSERS:")
        for b in lost_bets:
            print(
                f"    - {b['event_name']} | {b['selection']} "
                f"@ {float(b['decimal_odds']):.2f} | P&L: ${b['profit_loss']:+,.2f}"
            )

    if void_bets:
        print("\n  VOIDED:")
        for b in void_bets:
            print(
                f"    ~ {b['event_name']} | {b['selection']} "
                f"@ {float(b['decimal_odds']):.2f}"
            )


if __name__ == "__main__":
    main()

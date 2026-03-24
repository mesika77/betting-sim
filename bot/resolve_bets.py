"""Evening bet resolution script for betting-sim.

Run every evening at 23:55 UTC by GitHub Actions to:
1. Get today's pending bets from the DB
2. Fetch scores from The Odds API for each relevant sport
3. Resolve each bet as won / lost / void
4. Update each bet's result and profit_loss in the DB
5. Calculate daily P&L
6. Write bankroll_history and daily_summary records
7. Print a clear summary to stdout
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

BASE_URL = "https://api.the-odds-api.com/v4/"
ORIGINAL_BANKROLL = 5000.00


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def fetch_scores(sport_key: str) -> list[dict]:
    """Fetch completed scores for a given sport key from The Odds API.

    Uses daysFrom=1 to capture scores from the last 24 hours.

    Returns an empty list on any error (so caller can safely void bets).
    """
    try:
        key = get_api_key()
    except ValueError as exc:
        print(f"[resolve_bets] ERROR — cannot fetch scores: {exc}")
        return []

    url = f"{BASE_URL}sports/{sport_key}/scores/"
    params = {
        "apiKey": key,
        "daysFrom": 1,
        "dateFormat": "iso",
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
    except requests.RequestException as exc:
        print(f"[resolve_bets] WARNING — network error fetching scores for '{sport_key}': {exc}")
        return []

    remaining = resp.headers.get("x-requests-remaining", "unknown")
    print(f"[resolve_bets] Scores fetched for '{sport_key}' | API quota remaining: {remaining}")

    if resp.status_code != 200:
        print(
            f"[resolve_bets] WARNING — HTTP {resp.status_code} for sport '{sport_key}': "
            f"{resp.text[:200]}"
        )
        return []

    try:
        return resp.json()
    except ValueError as exc:
        print(f"[resolve_bets] WARNING — invalid JSON for sport '{sport_key}': {exc}")
        return []


# ---------------------------------------------------------------------------
# Score-matching helpers
# ---------------------------------------------------------------------------

def _normalise(s: str) -> str:
    """Lower-case and strip whitespace for fuzzy team-name comparison."""
    return s.strip().lower()


def find_score_event(event_name: str, scores: list[dict]) -> dict | None:
    """Find the score object whose home_team + away_team matches event_name.

    event_name format: "Home Team vs Away Team"
    score object format: {home_team, away_team, scores: [{name, score}], completed, ...}

    Returns None if no match found.
    """
    # Parse event_name — be lenient about the separator
    sep = " vs "
    if sep not in event_name:
        # Try case-insensitive
        lower = event_name.lower()
        if " vs " not in lower:
            return None
        idx = lower.index(" vs ")
        home_part = event_name[:idx]
        away_part = event_name[idx + 4:]
    else:
        idx = event_name.index(sep)
        home_part = event_name[:idx]
        away_part = event_name[idx + len(sep):]

    norm_home = _normalise(home_part)
    norm_away = _normalise(away_part)

    for event in scores:
        api_home = _normalise(event.get("home_team", ""))
        api_away = _normalise(event.get("away_team", ""))
        if api_home == norm_home and api_away == norm_away:
            return event

    return None


def _parse_scores(score_objects: list[dict]) -> dict[str, float]:
    """Convert [{name, score}, ...] into {team_name: numeric_score}.

    Skips entries with non-numeric or missing scores.
    """
    result: dict[str, float] = {}
    for entry in score_objects or []:
        name = entry.get("name", "")
        raw = entry.get("score")
        if raw is None:
            continue
        try:
            result[name] = float(raw)
        except (ValueError, TypeError):
            pass
    return result


def determine_h2h_winner(score_event: dict) -> str | None:
    """Return the winning team's name from a completed score event.

    Returns None if scores are missing, incomplete, or a draw (no winner).
    """
    score_objects = score_event.get("scores") or []
    scores = _parse_scores(score_objects)

    if len(scores) < 2:
        return None

    teams = list(scores.keys())
    score_a = scores[teams[0]]
    score_b = scores[teams[1]]

    if score_a == score_b:
        # Draw — no h2h winner
        return None
    return teams[0] if score_a > score_b else teams[1]


def determine_totals_result(score_event: dict, selection: str) -> str:
    """Determine won/lost for a totals (over/under) market.

    Args:
        score_event: The completed score dict from The Odds API.
        selection: e.g. "Over 2.5" or "Under 47.5"

    Returns 'won', 'lost', or 'void' if the selection cannot be parsed.
    """
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

    score_objects = score_event.get("scores") or []
    scores = _parse_scores(score_objects)

    if not scores:
        return "void"

    total = sum(scores.values())

    if direction == "over":
        return "won" if total > line else "lost"
    else:  # under
        return "won" if total < line else "lost"


# ---------------------------------------------------------------------------
# Bet resolution
# ---------------------------------------------------------------------------

def resolve_bet(bet: dict, scores_cache: dict[str, list[dict]]) -> tuple[str, float]:
    """Resolve a single bet and return (result, profit_loss).

    Args:
        bet: A bet dict from the DB.
        scores_cache: Mutable dict mapping sport_key -> list of score objects.
                      This function will populate missing entries.

    Returns:
        (result, profit_loss) where result is 'won', 'lost', or 'void'.
    """
    sport_key = bet.get("sport", "")
    event_name = bet.get("event_name", "")
    market = bet.get("market", "").lower()
    selection = bet.get("selection", "")
    decimal_odds = float(bet.get("decimal_odds", 1.0))
    stake = float(bet.get("stake", 0.0))

    # Fetch scores for this sport (cached)
    if sport_key not in scores_cache:
        scores_cache[sport_key] = fetch_scores(sport_key)

    scores = scores_cache[sport_key]

    # Find the matching event
    score_event = find_score_event(event_name, scores)

    if score_event is None:
        print(f"  [VOID] Event not found in scores: '{event_name}' ({sport_key})")
        return "void", 0.0

    if not score_event.get("completed", False):
        print(f"  [VOID] Event not yet completed: '{event_name}'")
        return "void", 0.0

    # Market-specific resolution
    # Normalise market label — The Odds API uses "Match Winner" for h2h in some regions
    is_h2h = "h2h" in market or "match winner" in market
    is_totals = "total" in market or "over/under" in market
    is_spreads = "spread" in market or "handicap" in market

    if is_spreads:
        # Spreads are complex to resolve accurately — void for safety
        print(f"  [VOID] Spreads market not resolved (voided for safety): '{event_name}'")
        result = "void"

    elif is_h2h:
        winner = determine_h2h_winner(score_event)
        if winner is None:
            # Draw — h2h bets on either team are losers in a standard market
            print(f"  [LOST] No h2h winner (draw): '{event_name}'")
            result = "lost"
        elif _normalise(selection) == _normalise(winner):
            print(f"  [WON] '{selection}' won: '{event_name}'")
            result = "won"
        else:
            print(f"  [LOST] '{selection}' lost (winner was '{winner}'): '{event_name}'")
            result = "lost"

    elif is_totals:
        result = determine_totals_result(score_event, selection)
        print(f"  [{result.upper()}] Totals '{selection}': '{event_name}'")

    else:
        # Unknown market — void
        print(f"  [VOID] Unrecognised market '{market}': '{event_name}'")
        result = "void"

    # Calculate profit/loss
    if result == "won":
        profit_loss = round(stake * (decimal_odds - 1), 2)
    elif result == "lost":
        profit_loss = round(-stake, 2)
    else:  # void
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

    # Step 1: Get pending bets
    pending_bets = get_pending_bets()

    if not pending_bets:
        print("[resolve_bets] No pending bets found. Nothing to resolve. Exiting cleanly.")
        return

    print(f"[resolve_bets] Found {len(pending_bets)} pending bet(s) to resolve.\n")

    # Step 2 & 3: Fetch scores and resolve each bet
    scores_cache: dict[str, list[dict]] = {}
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

        # Step 4: Update the DB
        try:
            update_bet_result(bet_id, result, profit_loss)
        except Exception as exc:
            print(f"  [ERROR] Failed to update bet {bet_id} in DB: {exc}")
            # Still record the resolution locally for summary calculation
            # but mark it as void to be conservative with bankroll math
            result = "void"
            profit_loss = 0.0

        resolved_bets.append({**bet, "result": result, "profit_loss": profit_loss})
        print()

    # Step 5: Calculate daily stats
    won_bets = [b for b in resolved_bets if b["result"] == "won"]
    lost_bets = [b for b in resolved_bets if b["result"] == "lost"]
    void_bets = [b for b in resolved_bets if b["result"] == "void"]

    daily_pl = sum(b["profit_loss"] for b in resolved_bets)
    opening_balance = get_latest_bankroll()
    closing_balance = round(opening_balance + daily_pl, 2)
    win_rate = len(won_bets) / max(len(won_bets) + len(lost_bets), 1)

    # Step 6: Write bankroll_history and daily_summary
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

    # Step 7: Print summary
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
    print(f"  Total P&L     : ${closing_balance - ORIGINAL_BANKROLL:+,.2f}  "
          f"(vs original ${ORIGINAL_BANKROLL:,.2f})")
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

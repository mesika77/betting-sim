"""Detect sports arbitrage opportunities across bookmakers.

For every (event, market) combination:
  1. For each outcome, find the BEST (highest) decimal odds across all bookmakers.
  2. Calculate arb_ratio = sum(1 / best_odds) for all outcomes.
  3. If arb_ratio < 1.0, a guaranteed profit exists regardless of result.
  4. Optimal stake fraction per leg: stake_i = (1/odds_i) / arb_ratio

Returns a flat list of arb legs. Legs in the same arb share an arb_group_id.
"""

import uuid
from datetime import datetime


MARKET_MAP: dict[str, str] = {
    "ML": "Match Winner",
    "3-Way Result": "Match Winner",
    "Totals": "Total",
}


def find_arb_opportunities(
    events: list[dict],
    min_profit_pct: float = 0.5,
    min_odds: float = 1.05,
    max_arbs: int = 10,
) -> list[dict]:
    """Find arb opportunities across bookmakers.

    Returns a flat list of bet legs. Legs belonging to the same arb
    share an arb_group_id.
    """
    all_legs: list[dict] = []
    arbs_found = 0

    for event in events:
        if arbs_found >= max_arbs:
            break

        event_id = str(event.get("id", ""))
        home: str = event.get("home", "")
        away: str = event.get("away", "")
        event_name = f"{home} vs {away}"
        sport_slug: str = event.get("sport", {}).get("slug", "")
        raw_date: str = event.get("date", "")
        date_str = _parse_date(raw_date)
        bookmakers: dict = event.get("bookmakers", {})

        # best[(market_name, selection)] = (max_decimal_odds, bookmaker_name)
        best: dict[tuple, tuple] = {}

        for bm_name, markets in bookmakers.items():
            for market in markets:
                market_name: str = market.get("name", "")
                if market_name not in MARKET_MAP:
                    continue
                for odds_entry in market.get("odds", []):
                    selections = _parse_selections(market_name, odds_entry, home, away)
                    for selection, decimal_odds in selections:
                        if decimal_odds < min_odds:
                            continue
                        key = (market_name, selection)
                        # Take MAX odds per selection (best price available anywhere)
                        if key not in best or decimal_odds > best[key][0]:
                            best[key] = (decimal_odds, bm_name)

        # For each market type, check if any complete outcome set forms an arb
        for market_name in set(k[0] for k in best):
            market_label = MARKET_MAP[market_name]
            legs_raw = {
                sel: (odds, bm)
                for (mn, sel), (odds, bm) in best.items()
                if mn == market_name
            }

            for outcome_set in _get_outcome_groups(market_name, legs_raw, home, away):
                if not all(o in legs_raw for o in outcome_set):
                    continue

                arb_ratio = sum(1.0 / legs_raw[o][0] for o in outcome_set)
                if arb_ratio >= 1.0:
                    continue

                profit_pct = (1.0 / arb_ratio - 1.0) * 100
                if profit_pct < min_profit_pct:
                    continue

                group_id = str(uuid.uuid4())
                arbs_found += 1

                for outcome in outcome_set:
                    decimal_odds, bm_name = legs_raw[outcome]
                    stake_fraction = (1.0 / decimal_odds) / arb_ratio
                    all_legs.append({
                        "arb_group_id": group_id,
                        "event_id": event_id,
                        "sport": sport_slug,
                        "event_name": event_name,
                        "market": market_label,
                        "selection": outcome,
                        "decimal_odds": round(decimal_odds, 4),
                        "implied_prob": round(1.0 / decimal_odds, 6),
                        "bookmaker": bm_name,
                        "arb_ratio": round(arb_ratio, 6),
                        "profit_pct": round(profit_pct, 4),
                        "stake_fraction": round(stake_fraction, 6),
                        "date": date_str,
                        "commence_time": raw_date,
                    })

                if arbs_found >= max_arbs:
                    break

    # Sort legs so highest-profit arbs appear first
    all_legs.sort(key=lambda x: x["profit_pct"], reverse=True)
    return all_legs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_outcome_groups(
    market_name: str,
    legs: dict,
    home: str,
    away: str,
) -> list[list[str]]:
    """Return lists of selection names that must ALL be covered for an arb."""
    if market_name == "ML":
        return [[home, away]]
    elif market_name == "3-Way Result":
        return [[home, "Draw", away]]
    elif market_name == "Totals":
        # Pair Over/Under by handicap value — handicap must match across bookmakers
        handicaps: set[str] = set()
        for sel in legs:
            if sel.startswith("Over "):
                handicaps.add(sel[5:])
            elif sel.startswith("Under "):
                handicaps.add(sel[6:])
        return [
            [f"Over {hdp}", f"Under {hdp}"]
            for hdp in handicaps
            if f"Over {hdp}" in legs and f"Under {hdp}" in legs
        ]
    return []


def _parse_selections(
    market_name: str,
    odds_entry: dict,
    home: str,
    away: str,
) -> list[tuple[str, float]]:
    """Extract (selection_name, decimal_odds) pairs from one odds entry."""
    results: list[tuple[str, float]] = []

    if market_name == "ML":
        for key, name in (("home", home), ("away", away)):
            val = odds_entry.get(key)
            if val is not None:
                try:
                    results.append((name, float(val)))
                except (TypeError, ValueError):
                    pass

    elif market_name == "3-Way Result":
        for key, name in (("home", home), ("draw", "Draw"), ("away", away)):
            val = odds_entry.get(key)
            if val is not None:
                try:
                    results.append((name, float(val)))
                except (TypeError, ValueError):
                    pass

    elif market_name == "Totals":
        hdp = odds_entry.get("hdp")
        if hdp is not None:
            for direction in ("over", "under"):
                val = odds_entry.get(direction)
                if val is not None:
                    try:
                        results.append((f"{direction.capitalize()} {hdp}", float(val)))
                    except (TypeError, ValueError):
                        pass

    return results


def _parse_date(raw: str) -> str:
    """Extract YYYY-MM-DD from an ISO 8601 timestamp string."""
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return raw[:10] if len(raw) >= 10 else ""

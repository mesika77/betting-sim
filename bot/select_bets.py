"""Select the best bets from a list of normalized event dicts.

Works with the odds-api.io response format produced by fetch_odds.py.

Provides:
    select_best_bets(events, min_prob, max_bets, min_odds) -> list[dict]
"""

from datetime import datetime


# odds-api.io market name → human-readable label stored in the DB
MARKET_MAP: dict[str, str] = {
    "ML": "Match Winner",
    "3-Way Result": "Match Winner",
    "Totals": "Total",
    # Spread is intentionally omitted — too complex to resolve accurately
}


def select_best_bets(
    events: list[dict],
    min_prob: float = 0.65,
    max_bets: int = 20,
    min_odds: float = 1.05,
) -> list[dict]:
    """Rank and filter same-day events into a shortlist of best bets.

    Algorithm
    ---------
    For every (event, market, selection) triple across all bookmakers:
      1. Take the MINIMUM decimal odds available (= highest implied probability).
      2. Compute implied_prob = 1 / decimal_odds.
      3. Keep only selections where implied_prob >= min_prob.
    Sort survivors descending by implied_prob, return top max_bets.

    Returns
    -------
    List of dicts with keys:
        event_id, sport, event_name, market, selection,
        decimal_odds, implied_prob, date, commence_time
    """
    # best_odds[(event_id, market_label, selection)] = min decimal_odds seen
    best_odds: dict[tuple, float] = {}
    meta: dict[tuple, tuple] = {}  # key -> (sport_slug, event_name, date_str, commence_time)

    for event in events:
        event_id = str(event.get("id", ""))
        home: str = event.get("home", "")
        away: str = event.get("away", "")
        event_name = f"{home} vs {away}"
        sport_slug: str = event.get("sport", {}).get("slug", "")

        raw_date: str = event.get("date", "")
        date_str = _parse_date(raw_date)
        commence_time = raw_date  # stored as ISO string

        bookmakers: dict = event.get("bookmakers", {})
        for _bm_name, markets in bookmakers.items():
            for market in markets:
                market_name: str = market.get("name", "")
                market_label = MARKET_MAP.get(market_name)
                if market_label is None:
                    continue  # unsupported market — skip

                for odds_entry in market.get("odds", []):
                    selections = _parse_selections(market_name, odds_entry, home, away)
                    for selection, decimal_odds in selections:
                        if decimal_odds <= 1.0 or decimal_odds < min_odds:
                            continue

                        key = (event_id, market_label, selection)
                        if key not in best_odds or decimal_odds < best_odds[key]:
                            best_odds[key] = decimal_odds
                            meta[key] = (sport_slug, event_name, date_str, commence_time)

    candidates: list[dict] = []
    for (event_id, market_label, selection), decimal_odds in best_odds.items():
        implied_prob = 1.0 / decimal_odds
        if implied_prob < min_prob:
            continue

        sport_slug, event_name, date_str, commence_time = meta[(event_id, market_label, selection)]
        candidates.append(
            {
                "event_id": event_id,
                "sport": sport_slug,
                "event_name": event_name,
                "market": market_label,
                "selection": selection,
                "decimal_odds": round(decimal_odds, 4),
                "implied_prob": round(implied_prob, 6),
                "date": date_str,
                "commence_time": commence_time,
            }
        )

    candidates.sort(key=lambda b: b["implied_prob"], reverse=True)
    return candidates[:max_bets]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_selections(
    market_name: str,
    odds_entry: dict,
    home: str,
    away: str,
) -> list[tuple[str, float]]:
    """Extract (selection_name, decimal_odds) pairs from one odds entry.

    odds-api.io formats by market:
      ML            : {home, away}
      3-Way Result  : {home, draw, away}
      Totals        : {hdp, over, under}
    """
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

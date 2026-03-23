"""Select the best bets from a list of raw Odds API event dicts.

Provides:
    select_best_bets(events, min_prob, max_bets) -> list[dict]
"""

from datetime import datetime


# Human-readable labels for market keys returned by The Odds API
MARKET_LABELS: dict[str, str] = {
    "h2h": "Match Winner",
    "spreads": "Spread",
    "totals": "Total",
}


def select_best_bets(
    events: list[dict],
    min_prob: float = 0.65,
    max_bets: int = 20,
) -> list[dict]:
    """Rank and filter same-day events into a shortlist of best bets.

    Algorithm
    ---------
    For every (event, market, selection) triple across all bookmakers:
      1. Take the MAXIMUM decimal odds available (best payout for the bettor).
      2. Compute implied_prob = 1 / decimal_odds.
      3. Keep only selections where implied_prob >= min_prob.
    Sort the survivors descending by implied_prob and return the top max_bets.

    Parameters
    ----------
    events    : Raw event dicts from fetch_same_day_odds().
    min_prob  : Minimum implied probability to include (default 0.65).
    max_bets  : Maximum number of bets to return (default 20).

    Returns
    -------
    List of dicts, each with keys:
        event_id, sport, event_name, market, selection,
        decimal_odds, implied_prob, date
    """
    # best_odds[(event_id, market_key, selection_name)] = max decimal_odds seen
    best_odds: dict[tuple[str, str, str], float] = {}
    # meta[(event_id, market_key, selection_name)] = (sport_key, event_name, date_str)
    meta: dict[tuple[str, str, str], tuple[str, str, str]] = {}

    for event in events:
        event_id: str = event.get("id", "")
        sport_key: str = event.get("sport_key", "")
        home: str = event.get("home_team", "")
        away: str = event.get("away_team", "")
        event_name: str = f"{home} vs {away}"

        commence_raw: str = event.get("commence_time", "")
        date_str: str = _parse_date(commence_raw)

        bookmakers: list[dict] = event.get("bookmakers", [])
        for bookmaker in bookmakers:
            markets: list[dict] = bookmaker.get("markets", [])
            for market in markets:
                market_key: str = market.get("key", "")
                outcomes: list[dict] = market.get("outcomes", [])
                for outcome in outcomes:
                    selection: str = outcome.get("name", "")
                    price = outcome.get("price")

                    if price is None:
                        continue
                    try:
                        decimal_odds = float(price)
                    except (TypeError, ValueError):
                        continue

                    # Skip invalid odds
                    if decimal_odds <= 1.0:
                        continue

                    key = (event_id, market_key, selection)
                    if key not in best_odds or decimal_odds > best_odds[key]:
                        best_odds[key] = decimal_odds
                        meta[key] = (sport_key, event_name, date_str)

    # Build candidate list, applying the min_prob filter
    candidates: list[dict] = []
    for (event_id, market_key, selection), decimal_odds in best_odds.items():
        implied_prob = 1.0 / decimal_odds
        if implied_prob < min_prob:
            continue

        sport_key, event_name, date_str = meta[(event_id, market_key, selection)]
        market_label = MARKET_LABELS.get(market_key, market_key)

        candidates.append(
            {
                "event_id": event_id,
                "sport": sport_key,
                "event_name": event_name,
                "market": market_label,
                "selection": selection,
                "decimal_odds": round(decimal_odds, 4),
                "implied_prob": round(implied_prob, 6),
                "date": date_str,
            }
        )

    # Sort descending by implied probability (safest bets first)
    candidates.sort(key=lambda b: b["implied_prob"], reverse=True)

    return candidates[:max_bets]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_date(commence_raw: str) -> str:
    """Extract the YYYY-MM-DD portion of an ISO 8601 timestamp string.

    Returns an empty string if parsing fails.
    """
    if not commence_raw:
        return ""
    try:
        # Handles both 'Z' and '+00:00' suffixes
        commence_str = commence_raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(commence_str)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        # Fallback: take the date portion directly from the string
        return commence_raw[:10] if len(commence_raw) >= 10 else ""

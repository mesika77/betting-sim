"""Main morning script for daily bet simulation.

Run every morning by GitHub Actions to:
1. Get today's bankroll from DB
2. Fetch odds and select top bets
3. Apply proportional stake sizing
4. Write all bets to DB
5. Print summary to stdout (for GitHub Actions logs)
"""

from datetime import date

from bot.db import get_latest_bankroll, insert_bets
from bot.fetch_odds import fetch_same_day_odds
from bot.select_bets import select_best_bets


def apply_stakes(bets: list[dict], bankroll: float) -> list[dict]:
    """Apply proportional stake sizing to a list of bets.

    Algorithm:
    1. Use implied_prob as weights
    2. Calculate raw stake = (prob / sum_probs) * bankroll
    3. Apply bounds: stake = max($50, min(raw, bankroll * 0.20))
    4. If total exceeds bankroll, re-normalize all stakes

    Args:
        bets: List of bet dicts with at least 'implied_prob' key
        bankroll: Current bankroll amount

    Returns:
        List of bets with added 'stake' key (rounded to 2 decimals)
    """
    # Edge case: no bets
    if not bets:
        return []

    # Edge case: single bet
    if len(bets) == 1:
        bet = bets[0].copy()
        # For a single bet, use the stake bounds
        raw_stake = bankroll
        stake = max(50.0, min(raw_stake, bankroll * 0.20))
        bet["stake"] = round(stake, 2)
        return [bet]

    # Step 1: Get weights from implied probabilities
    weights = [b["implied_prob"] for b in bets]
    total_weight = sum(weights)

    # Step 2: Calculate raw stakes and apply bounds
    bets_with_stakes = []
    for bet in bets:
        bet_copy = bet.copy()
        raw_stake = (bet["implied_prob"] / total_weight) * bankroll
        # Floor at $50, cap at 20% of bankroll
        stake = max(50.0, min(raw_stake, bankroll * 0.20))
        bet_copy["stake"] = round(stake, 2)
        bets_with_stakes.append(bet_copy)

    # Step 3: Re-normalize if total stakes exceed bankroll
    total_staked = sum(b["stake"] for b in bets_with_stakes)
    if total_staked > bankroll:
        scale = bankroll / total_staked
        for bet in bets_with_stakes:
            bet["stake"] = round(bet["stake"] * scale, 2)

    return bets_with_stakes


def main():
    """Main entry point: fetch odds, select bets, size stakes, write to DB."""
    # Step 1: Get today's bankroll
    bankroll = get_latest_bankroll()
    print(f"Today's bankroll: ${bankroll:,.2f}")

    # Step 2: Fetch same-day odds and select best bets
    events = fetch_same_day_odds()
    bets = select_best_bets(events)

    if not bets:
        print("No qualifying bets found today (no events meeting criteria)")
        return

    # Step 3: Apply stake sizing
    bets = apply_stakes(bets, bankroll)

    # Step 4: Prepare DB records
    today = date.today().isoformat()
    db_records = [
        {
            "date": today,
            "sport": b["sport"],
            "event_name": b["event_name"],
            "market": b["market"],
            "selection": b["selection"],
            "decimal_odds": b["decimal_odds"],
            "implied_prob": b["implied_prob"],
            "stake": b["stake"],
        }
        for b in bets
    ]

    # Step 5: Write to DB
    insert_bets(db_records)

    # Step 6: Print summary
    print(f"\nPlaced {len(bets)} simulated bets:")
    for b in bets:
        print(
            f"  {b['sport']}: {b['event_name']} | {b['selection']} "
            f"@ {b['decimal_odds']:.2f} | prob={b['implied_prob']:.1%} | ${b['stake']:,.2f}"
        )
    total_staked = sum(b["stake"] for b in bets)
    print(f"\nTotal staked: ${total_staked:,.2f}")


if __name__ == "__main__":
    main()

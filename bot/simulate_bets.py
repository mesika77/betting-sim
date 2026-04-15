"""Main morning script for daily arb bet simulation.

Run every morning by GitHub Actions to:
1. Get today's bankroll from DB
2. Fetch odds and detect arb opportunities across bookmakers
3. Apply arb-optimal stake sizing (budget per arb group, split by leg fraction)
4. Write all bet legs to DB
5. Print summary to stdout (for GitHub Actions logs)
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bot.db import get_latest_bankroll, insert_bets
from bot.fetch_odds import fetch_same_day_odds
from bot.select_bets import find_arb_opportunities


def apply_stakes(legs: list[dict], bankroll: float) -> list[dict]:
    """Apply arb-optimal stake sizing to arb legs.

    Algorithm:
    1. Group legs by arb_group_id.
    2. Allocate a budget to each arb group proportional to its profit_pct.
    3. Cap each group budget at 20% of bankroll, floor at $100.
    4. Re-normalize if total exceeds bankroll.
    5. Calculate each leg's stake = budget * stake_fraction.

    Args:
        legs: Flat list of arb leg dicts (each has arb_group_id, stake_fraction, profit_pct).
        bankroll: Current bankroll amount.

    Returns:
        Legs with added 'stake' key (rounded to 2 decimals).
    """
    if not legs:
        return []

    # Group legs by arb_group_id
    groups: dict[str, list[dict]] = {}
    for leg in legs:
        gid = leg["arb_group_id"]
        groups.setdefault(gid, []).append(leg)

    # Each group's profit_pct (all legs in a group share the same value)
    profit_pcts = {gid: group_legs[0]["profit_pct"] for gid, group_legs in groups.items()}
    total_profit = sum(profit_pcts.values()) or 1.0

    max_per_arb = bankroll * 0.20
    min_per_arb = 100.0

    # Allocate budget per group
    budgets: dict[str, float] = {
        gid: max(min_per_arb, min((pct / total_profit) * bankroll, max_per_arb))
        for gid, pct in profit_pcts.items()
    }

    # Re-normalize if total stakes exceed bankroll
    total = sum(budgets.values())
    if total > bankroll:
        scale = bankroll / total
        budgets = {gid: b * scale for gid, b in budgets.items()}

    # Apply stake to each leg
    result: list[dict] = []
    for gid, group_legs in groups.items():
        budget = budgets[gid]
        for leg in group_legs:
            leg_copy = leg.copy()
            leg_copy["stake"] = round(leg["stake_fraction"] * budget, 2)
            result.append(leg_copy)

    return result


def main():
    """Main entry point: fetch odds, detect arbs, size stakes, write to DB."""
    # Step 1: Get today's bankroll
    bankroll = get_latest_bankroll()
    print(f"Today's bankroll: ${bankroll:,.2f}")

    # Step 2: Fetch same-day odds and detect arb opportunities
    events = fetch_same_day_odds()
    legs = find_arb_opportunities(events)

    if not legs:
        print("No arb opportunities found today.")
        return

    # Step 3: Apply stake sizing
    legs = apply_stakes(legs, bankroll)

    # Step 4: Prepare DB records
    IDT = ZoneInfo("Asia/Jerusalem")
    today = datetime.now(tz=IDT).strftime("%Y-%m-%d")
    db_records = [
        {
            "date": today,
            "sport": leg["sport"],
            "event_name": leg["event_name"],
            "market": leg["market"],
            "selection": leg["selection"],
            "decimal_odds": leg["decimal_odds"],
            "implied_prob": leg["implied_prob"],
            "stake": leg["stake"],
            "commence_time": leg.get("commence_time"),
            "arb_group_id": leg["arb_group_id"],
            "bookmaker": leg["bookmaker"],
        }
        for leg in legs
    ]

    # Step 5: Write to DB
    insert_bets(db_records)

    # Step 6: Print summary grouped by arb
    groups: dict[str, list[dict]] = {}
    for leg in legs:
        groups.setdefault(leg["arb_group_id"], []).append(leg)

    print(f"\nFound {len(groups)} arb opportunity(ies) — {len(legs)} total legs:\n")
    for i, (gid, group_legs) in enumerate(groups.items(), 1):
        profit_pct = group_legs[0]["profit_pct"]
        arb_ratio = group_legs[0]["arb_ratio"]
        total_stake = sum(l["stake"] for l in group_legs)
        guaranteed_profit = round(total_stake * profit_pct / 100, 2)
        print(f"  Arb #{i} — {group_legs[0]['event_name']} | {group_legs[0]['market']}")
        print(f"    Profit: {profit_pct:.2f}% | Arb ratio: {arb_ratio:.4f} | "
              f"Total stake: ${total_stake:,.2f} | Guaranteed profit: ${guaranteed_profit:,.2f}")
        for leg in group_legs:
            print(f"    [{leg['bookmaker']}] {leg['selection']} @ {leg['decimal_odds']:.4f} "
                  f"→ stake ${leg['stake']:,.2f}")
        print()

    total_staked = sum(l["stake"] for l in legs)
    total_guaranteed = sum(
        sum(l["stake"] for l in gl) * gl[0]["profit_pct"] / 100
        for gl in groups.values()
    )
    print(f"Total staked: ${total_staked:,.2f}")
    print(f"Total guaranteed profit: ${total_guaranteed:,.2f}")


if __name__ == "__main__":
    main()

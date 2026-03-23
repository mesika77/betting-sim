"""Supabase database client wrapper for betting-sim.

This module provides a thin interface to Supabase tables:
- bets: individual bet records
- bankroll_history: daily bankroll snapshots
- daily_summary: daily summary statistics
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env if it exists
load_dotenv()

# Module-level client (lazy initialized)
_client: Client | None = None


def _get_client() -> Client:
    """Initialize and return the Supabase client (lazy initialization)."""
    global _client

    if _client is not None:
        return _client

    # Read environment variables
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set"
        )

    _client = create_client(url, key)
    return _client


def get_latest_bankroll() -> float:
    """Get the most recent closing_balance from bankroll_history.

    Returns 5000.0 if no history exists.
    """
    try:
        client = _get_client()
        response = client.table("bankroll_history").select("closing_balance").order(
            "date", desc=True
        ).limit(1).execute()

        if response.data and len(response.data) > 0:
            return float(response.data[0]["closing_balance"])

        return 5000.0
    except Exception as e:
        raise Exception(f"Failed to get latest bankroll: {e}") from e


def insert_bets(bets: list[dict]) -> None:
    """Insert a list of bet dicts into the bets table.

    Each dict should have keys:
    - date: date string (YYYY-MM-DD)
    - sport: string
    - event_name: string
    - market: string
    - selection: string
    - decimal_odds: float
    - implied_prob: float
    - stake: float

    result defaults to 'pending', profit_loss to None.
    """
    if not bets:
        return

    try:
        client = _get_client()

        # Add defaults to each bet
        bets_with_defaults = []
        for bet in bets:
            bet_copy = bet.copy()
            bet_copy.setdefault("result", "pending")
            bet_copy.setdefault("profit_loss", None)
            bets_with_defaults.append(bet_copy)

        response = client.table("bets").insert(bets_with_defaults).execute()
        if not response.data:
            raise Exception("Insert returned no data")
    except Exception as e:
        raise Exception(f"Failed to insert bets: {e}") from e


def update_bet_result(bet_id: str, result: str, profit_loss: float) -> None:
    """Update a single bet's result and profit_loss by id.

    Args:
        bet_id: UUID of the bet
        result: one of 'won', 'lost', 'void', 'pending'
        profit_loss: numerical profit/loss amount
    """
    try:
        client = _get_client()
        response = client.table("bets").update(
            {"result": result, "profit_loss": profit_loss}
        ).eq("id", bet_id).execute()

        if not response.data:
            raise Exception(f"No bet found with id {bet_id}")
    except Exception as e:
        raise Exception(f"Failed to update bet {bet_id}: {e}") from e


def insert_bankroll_history(record: dict) -> None:
    """Upsert a record into bankroll_history.

    Record keys:
    - date: date string (YYYY-MM-DD)
    - opening_balance: float
    - closing_balance: float
    - daily_pl: float
    - total_pl: float
    - num_bets: int
    - num_won: int
    - num_lost: int
    """
    try:
        client = _get_client()
        # Use upsert: on conflict (date), do update
        response = client.table("bankroll_history").upsert(record).execute()

        if not response.data:
            raise Exception("Upsert returned no data")
    except Exception as e:
        raise Exception(f"Failed to insert bankroll history: {e}") from e


def get_today_bets() -> list[dict]:
    """Return all bets for today (date == current date in UTC)."""
    try:
        client = _get_client()
        today = datetime.utcnow().strftime("%Y-%m-%d")

        response = client.table("bets").select("*").eq("date", today).execute()

        return response.data if response.data else []
    except Exception as e:
        raise Exception(f"Failed to get today's bets: {e}") from e


def get_pending_bets() -> list[dict]:
    """Return all bets with result == 'pending'."""
    try:
        client = _get_client()
        response = client.table("bets").select("*").eq("result", "pending").execute()

        return response.data if response.data else []
    except Exception as e:
        raise Exception(f"Failed to get pending bets: {e}") from e


def get_all_bets() -> list[dict]:
    """Return all bets ordered by date desc."""
    try:
        client = _get_client()
        response = client.table("bets").select("*").order("date", desc=True).execute()

        return response.data if response.data else []
    except Exception as e:
        raise Exception(f"Failed to get all bets: {e}") from e


def get_bankroll_history() -> list[dict]:
    """Return all bankroll_history rows ordered by date asc."""
    try:
        client = _get_client()
        response = client.table("bankroll_history").select("*").order(
            "date", desc=False
        ).execute()

        return response.data if response.data else []
    except Exception as e:
        raise Exception(f"Failed to get bankroll history: {e}") from e


def get_daily_summary() -> list[dict]:
    """Return all daily_summary rows ordered by date asc."""
    try:
        client = _get_client()
        response = client.table("daily_summary").select("*").order(
            "date", desc=False
        ).execute()

        return response.data if response.data else []
    except Exception as e:
        raise Exception(f"Failed to get daily summary: {e}") from e


def upsert_daily_summary(record: dict) -> None:
    """Upsert a record into daily_summary.

    Record keys:
    - date: date string (YYYY-MM-DD)
    - bankroll: float
    - daily_pl: float
    - win_rate: float
    - num_bets: int
    """
    try:
        client = _get_client()
        # Use upsert: on conflict (date), do update
        response = client.table("daily_summary").upsert(record).execute()

        if not response.data:
            raise Exception("Upsert returned no data")
    except Exception as e:
        raise Exception(f"Failed to upsert daily summary: {e}") from e

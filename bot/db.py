"""Neon PostgreSQL database client for betting-sim bot."""
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def _get_connection_string() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL environment variable is not set")
    return url


@contextmanager
def _get_conn() -> Generator:
    """Context manager that yields a psycopg2 connection and commits on exit."""
    conn = psycopg2.connect(_get_connection_string())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_latest_bankroll() -> float:
    """Return most recent closing_balance from bankroll_history. Defaults to 5000.0."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT closing_balance FROM bankroll_history ORDER BY date DESC LIMIT 1"
            )
            row = cur.fetchone()
            return float(row["closing_balance"]) if row else 5000.0


def insert_bets(bets: list[dict]) -> None:
    """Insert a list of bet dicts into the bets table."""
    if not bets:
        return
    with _get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO bets
                    (date, sport, event_name, market, selection, decimal_odds, implied_prob, stake, result, commence_time)
                VALUES
                    (%(date)s, %(sport)s, %(event_name)s, %(market)s, %(selection)s,
                     %(decimal_odds)s, %(implied_prob)s, %(stake)s, 'pending', %(commence_time)s)
                """,
                bets,
            )


def update_bet_result(bet_id: str, result: str, profit_loss: float) -> None:
    """Update a single bet's result and profit_loss by id."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE bets SET result = %s, profit_loss = %s WHERE id = %s",
                (result, profit_loss, bet_id),
            )


def insert_bankroll_history(record: dict) -> None:
    """Upsert a record into bankroll_history."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bankroll_history
                    (date, opening_balance, closing_balance, daily_pl, total_pl, num_bets, num_won, num_lost)
                VALUES
                    (%(date)s, %(opening_balance)s, %(closing_balance)s, %(daily_pl)s,
                     %(total_pl)s, %(num_bets)s, %(num_won)s, %(num_lost)s)
                ON CONFLICT (date) DO UPDATE SET
                    opening_balance = EXCLUDED.opening_balance,
                    closing_balance = EXCLUDED.closing_balance,
                    daily_pl        = EXCLUDED.daily_pl,
                    total_pl        = EXCLUDED.total_pl,
                    num_bets        = EXCLUDED.num_bets,
                    num_won         = EXCLUDED.num_won,
                    num_lost        = EXCLUDED.num_lost
                """,
                record,
            )


def get_today_bets() -> list[dict]:
    """Return all bets for today (UTC)."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM bets WHERE date = %s ORDER BY implied_prob DESC",
                (today,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_pending_bets() -> list[dict]:
    """Return all pending bets for today (UTC)."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM bets WHERE result = 'pending' AND date = %s",
                (today,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_all_bets() -> list[dict]:
    """Return all bets ordered by date desc."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM bets ORDER BY date DESC, implied_prob DESC")
            return [dict(row) for row in cur.fetchall()]


def get_bankroll_history() -> list[dict]:
    """Return all bankroll_history rows ordered by date asc."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM bankroll_history ORDER BY date ASC")
            return [dict(row) for row in cur.fetchall()]


def get_daily_summary() -> list[dict]:
    """Return all daily_summary rows ordered by date asc."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM daily_summary ORDER BY date ASC")
            return [dict(row) for row in cur.fetchall()]


def upsert_daily_summary(record: dict) -> None:
    """Upsert a record into daily_summary."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_summary (date, bankroll, daily_pl, win_rate, num_bets)
                VALUES (%(date)s, %(bankroll)s, %(daily_pl)s, %(win_rate)s, %(num_bets)s)
                ON CONFLICT (date) DO UPDATE SET
                    bankroll  = EXCLUDED.bankroll,
                    daily_pl  = EXCLUDED.daily_pl,
                    win_rate  = EXCLUDED.win_rate,
                    num_bets  = EXCLUDED.num_bets
                """,
                record,
            )

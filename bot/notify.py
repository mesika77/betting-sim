"""Telegram notification sender for betting-sim.

Usage:
    python bot/notify.py --morning   # Send morning bets summary
    python bot/notify.py --evening   # Send evening results + Excel attachment
"""

import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Bot

IDT = ZoneInfo("Asia/Jerusalem")


# ── Telegram helpers ──────────────────────────────────────────────────────────

async def send_message(token: str, chat_id: str, text: str,
                       document_path: str = None) -> None:
    """Send a text message and optionally attach a document."""
    bot = Bot(token=token)
    await bot.send_message(chat_id=chat_id, text=text)
    if document_path:
        with open(document_path, "rb") as f:
            await bot.send_document(chat_id=chat_id, document=f)


# ── Message builders ──────────────────────────────────────────────────────────

def build_morning_message() -> str:
    from bot.db import get_latest_bankroll, get_bets_for_date

    bankroll = get_latest_bankroll()
    now = datetime.now(tz=IDT)
    today_db = now.strftime("%Y-%m-%d")
    bets = get_bets_for_date(today_db)

    today_str = f"{now.strftime('%B')} {now.day}, {now.year}"
    num_bets = len(bets)

    # Count distinct sports
    sports = {b.get("sport", "") for b in bets if b.get("sport")}
    num_sports = len(sports)

    lines = [
        f"Bets Placed — {today_str}",
        "",
        f"Bankroll today: ${bankroll:,.2f}",
        f"Bets placed: {num_bets} across {num_sports} sport{'s' if num_sports != 1 else ''}",
    ]

    if bets:
        # All picks sorted by implied_prob desc
        sorted_bets = sorted(
            bets,
            key=lambda b: float(b.get("implied_prob") or 0),
            reverse=True,
        )

        bet_lines = []
        for b in sorted_bets:
            time_str = ""
            if b.get("commence_time"):
                try:
                    ct = datetime.fromisoformat(str(b["commence_time"]).replace("Z", "+00:00"))
                    time_str = f" [{ct.astimezone(IDT).strftime('%H:%M')}]"
                except Exception:
                    pass
            bet_lines.append(
                f"- {b['sport']}: {b['event_name']}{time_str} | {b['selection']} "
                f"@ {float(b['decimal_odds']):.2f} | {float(b['implied_prob']):.1%} | ${float(b['stake']):,.2f}"
            )

        bets_text = "\n".join(bet_lines)
        lines.append("")
        lines.append("All picks:")
        lines.append(bets_text)
    else:
        lines.append("")
        lines.append("No qualifying arbitrage bets found today.")

    lines.append("")
    lines.append("Results tonight at midnight.")

    return "\n".join(lines)


def build_evening_message() -> str:
    from bot.db import get_bets_for_date, get_bankroll_history

    now = datetime.now(tz=IDT)
    today_db = now.strftime("%Y-%m-%d")
    bets = get_bets_for_date(today_db)
    history = get_bankroll_history()

    today_str = f"{now.strftime('%B')} {now.day}, {now.year}"

    # Derive opening / closing bankroll from history
    opening = 0.0
    closing = 0.0
    total_pl = 0.0
    if history:
        # closing of previous day = opening of today
        if len(history) >= 2:
            opening = float(history[-2].get("closing_balance") or 0)
        elif len(history) == 1:
            opening = float(history[0].get("opening_balance") or 0)
        closing = float(history[-1].get("closing_balance") or 0)
        total_pl = float(history[-1].get("total_pl") or 0)

    day_pl = closing - opening
    day_pl_pct = (day_pl / opening * 100) if opening else 0.0

    # Bet stats
    num_bets = len(bets)
    won_bets = [b for b in bets if (b.get("result") or "").lower() == "won"]
    lost_bets = [b for b in bets if (b.get("result") or "").lower() == "lost"]
    void_bets = [b for b in bets if (b.get("result") or "").lower() == "void"]
    num_won = len(won_bets)
    num_lost = len(lost_bets)
    num_void = len(void_bets)
    win_rate = (num_won / (num_won + num_lost) * 100) if (num_won + num_lost) > 0 else 0.0

    # Best win / worst loss
    best_win_line = ""
    worst_loss_line = ""

    if won_bets:
        best = max(won_bets, key=lambda b: float(b.get("profit_loss") or 0))
        best_win_line = (
            f"Best win: {best.get('event_name', '')} — "
            f"${float(best.get('stake') or 0):,.2f} → "
            f"+${float(best.get('profit_loss') or 0):,.2f}"
        )

    if lost_bets:
        worst = min(lost_bets, key=lambda b: float(b.get("profit_loss") or 0))
        worst_loss_line = (
            f"Worst loss: {worst.get('event_name', '')} — "
            f"${float(worst.get('stake') or 0):,.2f} → "
            f"${float(worst.get('profit_loss') or 0):,.2f}"
        )

    # All-time win rate from full history
    all_time_won = sum(int(r.get("num_won") or 0) for r in history)
    all_time_bets = sum(int(r.get("num_bets") or 0) for r in history)
    all_time_wr = (all_time_won / all_time_bets * 100) if all_time_bets > 0 else 0.0

    day_pl_sign = "+" if day_pl >= 0 else ""
    total_pl_sign = "+" if total_pl >= 0 else ""

    lines = [
        f"Daily Results — {today_str}",
        "",
        f"Bankroll: ${opening:,.2f} → ${closing:,.2f}",
        f"Day P&L: {day_pl_sign}${day_pl:,.2f} ({day_pl_sign}{day_pl_pct:.1f}%)",
        "",
        (f"Bets: {num_bets} placed | {num_won} Won | {num_lost} Lost"
         f" | {num_void} Void | Win rate: {win_rate:.1f}%"),
    ]

    if best_win_line:
        lines.append("")
        lines.append(best_win_line)
    if worst_loss_line:
        lines.append(worst_loss_line)

    lines += [
        "",
        f"All-time: {total_pl_sign}${total_pl:,.2f} total P&L | {all_time_wr:.1f}% overall win rate",
        "",
        "[Excel report for today attached]",
    ]

    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    from bot.export_excel import generate_excel

    parser = argparse.ArgumentParser(description="Send Telegram bet notifications")
    parser.add_argument("--morning", action="store_true", help="Send morning bets summary")
    parser.add_argument("--evening", action="store_true", help="Send evening results")
    args = parser.parse_args()

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    if args.morning:
        text = build_morning_message()
        asyncio.run(send_message(token, chat_id, text))
    elif args.evening:
        text = build_evening_message()
        excel_path = generate_excel()
        asyncio.run(send_message(token, chat_id, text, excel_path))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

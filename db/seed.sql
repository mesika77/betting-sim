-- Initialize Day 0 bankroll record
-- This sets the starting bankroll to $5,000 on the day before tracking begins.
-- It establishes the baseline for all profit/loss calculations going forward.

INSERT INTO bankroll_history (date, opening_balance, closing_balance, daily_pl, total_pl, num_bets, num_won, num_lost)
VALUES (CURRENT_DATE - INTERVAL '1 day', 5000.00, 5000.00, 0.00, 0.00, 0, 0, 0)
ON CONFLICT (date) DO NOTHING;

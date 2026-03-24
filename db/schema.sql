-- Schema for Neon PostgreSQL (previously Supabase)
-- Run this in the Neon SQL Editor at console.neon.tech
-- Note: RLS policies are not needed with Neon (dashboard uses server-side queries)

-- bets table
CREATE TABLE bets (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date           DATE NOT NULL,
  sport          TEXT,
  event_name     TEXT,
  market         TEXT,
  selection      TEXT,
  decimal_odds   NUMERIC(6,3),
  implied_prob   NUMERIC(5,4),
  stake          NUMERIC(10,2),
  result         TEXT DEFAULT 'pending',   -- 'pending' | 'won' | 'lost' | 'void'
  profit_loss    NUMERIC(10,2),
  created_at     TIMESTAMPTZ DEFAULT now()
);

-- bankroll_history table (one row per day)
CREATE TABLE bankroll_history (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date            DATE UNIQUE NOT NULL,
  opening_balance NUMERIC(10,2),
  closing_balance NUMERIC(10,2),
  daily_pl        NUMERIC(10,2),
  total_pl        NUMERIC(10,2),
  num_bets        INT,
  num_won         INT,
  num_lost        INT
);

-- daily_summary table
CREATE TABLE daily_summary (
  date        DATE PRIMARY KEY,
  bankroll    NUMERIC(10,2),
  daily_pl    NUMERIC(10,2),
  win_rate    NUMERIC(5,4),
  num_bets    INT
);

-- Create indexes for performance
CREATE INDEX idx_bets_date ON bets(date);
CREATE INDEX idx_bets_result ON bets(result);
CREATE INDEX idx_bankroll_history_date ON bankroll_history(date);

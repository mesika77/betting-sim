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

-- Enable Row Level Security
ALTER TABLE bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE bankroll_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_summary ENABLE ROW LEVEL SECURITY;

-- RLS Policy: anon users can SELECT all rows from bets
CREATE POLICY bets_select_anon ON bets
  FOR SELECT
  TO anon
  USING (true);

-- RLS Policy: anon users can SELECT all rows from bankroll_history
CREATE POLICY bankroll_history_select_anon ON bankroll_history
  FOR SELECT
  TO anon
  USING (true);

-- RLS Policy: anon users can SELECT all rows from daily_summary
CREATE POLICY daily_summary_select_anon ON daily_summary
  FOR SELECT
  TO anon
  USING (true);

-- Create indexes for performance
CREATE INDEX idx_bets_date ON bets(date);
CREATE INDEX idx_bets_result ON bets(result);
CREATE INDEX idx_bankroll_history_date ON bankroll_history(date);

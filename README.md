# betting-sim

An automated **sports arbitrage** simulation bot. Detects guaranteed-profit opportunities across multiple bookmakers daily and simulates execution against a virtual $5,000 bankroll. No real money involved.

## What is arbitrage betting?

When different bookmakers price the same event differently, you can back all outcomes across them such that:

```
sum(1 / best_odds for each outcome) < 1.0
```

The gap below 1.0 is **guaranteed profit regardless of result**. For example:

| Bookmaker | Selection | Odds | Implied prob |
|-----------|-----------|------|-------------|
| Bet365 | Team A win | 2.10 | 47.6% |
| Pinnacle | Team B win | 2.10 | 47.6% |
| **Total** | | | **95.2%** → 4.8% profit |

Stake $476 on Team A + $476 on Team B = $952 total. Whoever wins pays $1,000. Guaranteed $48 profit.

## Architecture

```
GitHub Actions (cron)
  ├── 08:05 Israel time → simulate_bets.py  → detect arbs, write to DB, Telegram alert
  └── 23:55 Israel time → resolve_bets.py   → ESPN scores, update P&L, Telegram results

odds-api.io ──→ fetch_odds.py ──→ select_bets.py ──→ simulate_bets.py
                                                           │
                                                    Neon PostgreSQL
                                                           │
                                              Next.js Dashboard (Vercel)
```

## How it works

### Morning (08:05 Israel time)
1. Fetch same-day events across football, basketball, baseball, ice-hockey from **10 bookmakers** in parallel
2. For each event/market, find the **best (highest) odds** for each outcome across all bookmakers
3. Check if `arb_ratio = sum(1/best_odds) < 1.0` → guaranteed profit
4. Size stakes: allocate budget per arb (proportional to profit %), split across legs using `stake_fraction = (1/odds_i) / arb_ratio`
5. Insert all legs to DB, send Telegram summary

### Evening (11:55 PM UTC)
1. Fetch final scores from ESPN public API (no key required)
2. Resolve each leg as won/lost/void, calculate profit_loss
3. Update bankroll history
4. Send Telegram results

### Arb math
```
arb_ratio    = sum(1 / best_odds_i)          # must be < 1.0
profit_pct   = (1 / arb_ratio - 1) * 100
stake_i      = budget × (1/odds_i) / arb_ratio
guaranteed   = total_budget × profit_pct / 100
```

## Project structure

```
bot/
  fetch_odds.py      # Multi-bookmaker odds fetching (parallel, rate-limit aware)
  select_bets.py     # Arb detection across bookmakers
  simulate_bets.py   # Stake sizing + DB write
  resolve_bets.py    # Evening resolution via ESPN
  db.py              # Neon PostgreSQL client
  notify.py          # Telegram alerts
  export_excel.py    # Daily Excel report

db/
  schema.sql                      # Full DB schema
  migrate_add_arb_columns.sql     # Adds arb_group_id + bookmaker columns
  migrate_add_commence_time.sql
```

## Database schema (Neon — betsim)

**`bets`**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| date | DATE | Bet date |
| sport | TEXT | football / basketball / baseball / ice-hockey |
| event_name | TEXT | "Team A vs Team B" |
| market | TEXT | Match Winner / Total |
| selection | TEXT | Team name / Over 2.5 / etc |
| decimal_odds | NUMERIC | Best odds found for this leg |
| implied_prob | NUMERIC | 1 / decimal_odds |
| stake | NUMERIC | Dollar amount staked |
| bookmaker | TEXT | Which bookmaker offers these odds |
| arb_group_id | UUID | Links legs of the same arb together |
| result | TEXT | pending / won / lost / void |
| profit_loss | NUMERIC | Net P&L for this leg |
| commence_time | TIMESTAMPTZ | Game start time |

**`bankroll_history`** — one row per day: opening/closing balance, daily P&L, total P&L

**`daily_summary`** — date, bankroll, daily_pl, win_rate, num_bets

## Bookmakers

odds-api.io is queried with: `1xbet, 22Bet, bet365, pinnacle, williamhill, unibet, betway, bwin, marathonbet, betfair`

More bookmakers = more price divergence = more arb opportunities.

## Setup

### 1. Clone & install
```bash
git clone https://github.com/mesika77/betting-sim.git
cd betting-sim
pip install -r requirements.txt
```

### 2. Environment variables
```env
ODDS_API_KEY=your_odds_api_io_key
DATABASE_URL=postgresql://user:pass@host/betsim?sslmode=require
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Run DB migrations
In Neon SQL editor (console.neon.tech), run `db/schema.sql` then any `db/migrate_*.sql` files in order.

### 4. GitHub Actions secrets
Add these in Settings → Secrets → Actions:
- `ODDS_API_KEY`
- `DATABASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 5. Deploy dashboard
```bash
cd dashboard && npx vercel --prod
```
Add `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in Vercel dashboard.

## Configuration

**`bot/fetch_odds.py`**
- `BOOKMAKERS` — comma-separated list of bookmakers to query
- `QUOTA_RESERVE = 5` — stop fetching if API quota drops to this level
- `_MAX_RETRIES = 3` — retries on 429, using `Retry-After` header

**`bot/select_bets.py`**
- `min_profit_pct = 0.5` — minimum arb profit % to include (default 0.5%)
- `max_arbs = 10` — max arb opportunities per day

**`bot/simulate_bets.py`** (in `apply_stakes`)
- `max_per_arb = bankroll * 0.20` — max 20% of bankroll per arb
- `min_per_arb = 100.0` — minimum $100 budget per arb

## Why this strategy works (vs single-bet)

The previous approach (betting on highest implied probability) had a 90% win rate but still lost money. At odds of 1.09 (implied 92% probability), each $100 bet only nets $9 on a win but loses $100 on a loss — negative expected value after vig.

Arbitrage eliminates this: profit is locked in before the game starts, regardless of outcome.

## Real-money roadmap

1. **Simulator phase** (current) — validate arb detection logic, measure theoretical P&L
2. **US deployment** — New York or New Jersey (multiple legal sportsbooks available)
3. **Phase 1: Matched betting** — extract $3–5k from welcome bonuses before arbing
4. **Phase 2: Live arb** — run between DraftKings, FanDuel, BetMGM, Caesars, BetRivers, etc.

Note: Betfair Exchange is not available in the US, so there is no permanent sharp-side anchor. Accounts will eventually get limited — the strategy is to rotate across as many books as possible.

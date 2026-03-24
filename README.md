# betting-sim

An automated betting simulation bot that places and resolves daily bets based on sports odds data. **This is a simulated betting system using virtual money—no real funds are involved.**

## Overview

betting-sim is a fully automated daily betting workflow:

1. **Morning (8:05 AM UTC)**: Fetches today's sports odds from The Odds API, selects the best bets, sizes stakes proportionally to bankroll, and writes bets to the database
2. **Evening (11:55 PM UTC)**: Resolves today's bets against actual outcomes and generates a daily Excel report
3. **Notifications**: Sends Telegram messages each morning (bets placed) and evening (results summary)
4. **Dashboard**: Next.js web app displays bankroll history, cumulative P&L, and detailed bet records

All logic runs on **GitHub Actions** (cron-scheduled workflows), data lives in **Supabase**, and the dashboard deploys to **Vercel**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      GitHub Actions                              │
│  (Cron: 8:05 AM & 11:55 PM UTC)                                 │
│                                                                   │
│  Morning: simulate_bets.py → select bets & place stakes          │
│  Evening: resolve_bets.py → finalize daily results              │
│                                                                   │
└────────────────┬────────────────────────────────────────────────┘
                 │ (reads/writes)
                 ▼
         ┌─────────────────┐
         │   Supabase      │
         │   PostgreSQL    │
         │                 │
         │ - bets table    │
         │ - bankroll hist │
         │ - payouts       │
         └─────────────────┘
                 ▲
                 │ (reads)
         ┌───────┴─────────┐
         │                 │
    ┌────▼────┐      ┌────▼────┐
    │ Next.js │      │ Telegram │
    │Dashboard│      │  Bot     │
    │(Vercel) │      │          │
    └─────────┘      └──────────┘
```

**Components:**

- **Python Bot** (`bot/`): Core simulation logic
  - `fetch_odds.py`: Queries The Odds API for same-day events
  - `select_bets.py`: Ranks selections by implied probability (min 65%)
  - `simulate_bets.py`: Applies proportional stake sizing, inserts bets
  - `resolve_bets.py`: Checks actual outcomes, computes P&L
  - `notify.py`: Sends Telegram messages with results
  - `export_excel.py`: Generates daily Excel reports
  - `db.py`: Supabase client interface

- **GitHub Actions Workflows**: Cron-scheduled Python execution
  - `morning_run.yml`: 8:05 AM UTC (place bets + morning notification)
  - `evening_run.yml`: 11:55 PM UTC (resolve bets + evening notification)

- **Dashboard** (`dashboard/`): Next.js + Supabase client
  - Live bankroll tracking
  - Bet history with filters
  - Performance charts

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/betting-sim.git
cd betting-sim
```

### 2. Set up Supabase

1. Create a free account at [supabase.com](https://supabase.com)
2. Create a new project (choose a region close to you)
3. In the SQL editor, run the schema:
   ```
   supabase/schema.sql
   ```
4. Run the seed data:
   ```
   supabase/seed.sql
   ```
5. Copy your project URL and service role key from **Settings → API**:
   - `SUPABASE_URL`: Project URL (https://your-project.supabase.co)
   - `SUPABASE_SERVICE_KEY`: Service Role Key (starts with `eyJhb...`)

### 3. Get The Odds API key

1. Sign up for free at [the-odds-api.com](https://the-odds-api.com)
2. Copy your API key from the dashboard
   - Free tier: 500 requests/month
   - Each daily run uses ~2 requests (one per workflow)
3. This key enables `bot/fetch_odds.py` to pull live sports odds

### 4. Create Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Type `/newbot` and follow prompts to create a new bot
3. Copy the **Bot Token** (e.g., `123456:ABCdefGHIjklmno`)
4. Message [@userinfobot](https://t.me/userinfobot) to get your **Chat ID** (numeric ID)
   - Note: This is the chat ID where you'll receive notifications

### 5. Create `.env` file

Copy the example and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
ODDS_API_KEY=your_api_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 6. Install Python dependencies

```bash
pip install -r requirements.txt
```

Dependencies:
- `requests`: HTTP client for The Odds API
- `supabase`: Supabase Python client
- `python-telegram-bot`: Telegram bot API
- `openpyxl`: Excel file generation
- `python-dotenv`: Environment variable loading

### 7. Test locally

```bash
python -m bot.simulate_bets
```

This will:
- Fetch today's odds
- Select the best bets (implied prob ≥ 65%)
- Calculate stake sizes
- Insert bets into your Supabase database
- Print a summary to stdout

Check your database to verify bets were created.

### 8. Deploy dashboard to Vercel

```bash
cd dashboard
npx vercel --prod
```

When prompted, choose your GitHub account and connect the repository. Vercel will auto-detect the Next.js project.

After deployment, add environment variables in the **Vercel Dashboard** under **Settings → Environment Variables**:

```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

(Find the anon key in Supabase **Settings → API**)

### 9. Push to GitHub and enable Actions

```bash
git remote add origin https://github.com/yourusername/betting-sim.git
git push -u origin main
```

In your GitHub repository:

1. Go to **Settings → Secrets and variables → Actions**
2. Add the following secrets (exact names matter):
   - `ODDS_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

3. Go to **Actions** tab
4. Enable workflows (GitHub will prompt if they're disabled)

Workflows will now run automatically on schedule:
- **8:05 AM UTC**: `morning_run.yml` (place bets + notification)
- **11:55 PM UTC**: `evening_run.yml` (resolve bets + notification)

You can also manually trigger workflows from the **Actions** tab.

## Running Manually

Test each component locally:

```bash
# Place today's bets
python -m bot.simulate_bets

# Resolve today's bets (match outcomes)
python -m bot.resolve_bets

# Generate an Excel report of all bets
python -m bot.export_excel

# Send morning notification
python -m bot.notify --morning

# Send evening notification
python -m bot.notify --evening
```

Each script prints results to stdout and modifies the Supabase database as needed.

## Configuration

### Environment Variables

| Name | Used By | Description |
|------|---------|-------------|
| `ODDS_API_KEY` | `fetch_odds.py` | API key for The Odds API (free tier: 500 req/month) |
| `SUPABASE_URL` | All Python modules | Supabase project URL (e.g., `https://xxx.supabase.co`) |
| `SUPABASE_SERVICE_KEY` | All Python modules | Supabase service role key (full DB access) |
| `TELEGRAM_BOT_TOKEN` | `notify.py` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | `notify.py` | Your numeric Telegram user/chat ID |

(Dashboard uses `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` — see Step 8)

### Simulation Parameters

Adjust these in the Python modules:

**`bot/select_bets.py`**:
- `min_prob=0.65`: Minimum implied probability to include (65% = odds ≤ 1.54)
- `max_bets=20`: Maximum number of bets per day

Modify `select_best_bets()` call in `simulate_bets.py` to change defaults:

```python
bets = select_best_bets(events, min_prob=0.70, max_bets=15)
```

**`bot/simulate_bets.py`** (in `apply_stakes()` function):
- `$50 floor`: Minimum stake per bet
- `20% cap`: Maximum stake is 20% of daily bankroll

Modify `apply_stakes()` to adjust:

```python
stake = max(100.0, min(raw_stake, bankroll * 0.25))  # $100 floor, 25% cap
```

## How It Works

### Morning: Placing Bets

1. `github.com/yourusername/betting-sim` → GitHub Actions trigger (8:05 AM UTC)
2. `fetch_same_day_odds()` queries The Odds API for all events starting today
3. `select_best_bets()` ranks selections by implied probability, keeps top 20 (or fewer)
4. `apply_stakes()` sizes each bet:
   - Weight by implied probability
   - Apply bounds: `$50 ≤ stake ≤ (bankroll × 20%)`
   - Re-normalize if total exceeds bankroll
5. Insert bets into `bets` table with `status='placed'`
6. `notify.py --morning` sends a Telegram summary

### Evening: Resolving Bets

1. `github.com/yourusername/betting-sim` → GitHub Actions trigger (11:55 PM UTC)
2. `resolve_bets()` queries The Odds API for completed events
3. For each placed bet, check actual outcome and mark `status='won'` or `status='lost'`
4. Calculate P&L: `payout = stake * decimal_odds` (if won) or `payout = 0` (if lost)
5. Update `bankroll_history` table and current bankroll
6. `export_excel.py` generates daily report
7. `notify.py --evening` sends results + Excel to Telegram

### Dashboard

The Next.js dashboard (`dashboard/`) queries Supabase directly:
- **Bankroll Page**: Line chart of bankroll over time
- **Bets Page**: Searchable table of all bets with status, odds, stake, and payout
- **Stats**: Total bets, win rate, ROI, etc.

## Database Schema

Key tables in Supabase:

**`bets`**:
- `id`: UUID
- `date`: YYYY-MM-DD
- `sport`: sport key (e.g., 'baseball_mlb')
- `event_name`: "Team A vs Team B"
- `market`: "Match Winner", "Spread", etc.
- `selection`: "Team A", "Over 42.5", etc.
- `decimal_odds`: 1.95
- `stake`: 50.00
- `payout`: 97.50 (or null if unresolved)
- `status`: 'placed', 'won', 'lost'

**`bankroll_history`**:
- `date`: YYYY-MM-DD
- `opening_bankroll`: Starting balance for the day
- `closing_bankroll`: Ending balance (after all bets resolved)
- `daily_pl`: P&L for the day

**`bot_config`**:
- `current_bankroll`: Current available balance

See `supabase/schema.sql` for full schema.

## Troubleshooting

**Workflows not running?**
- Check GitHub **Settings → Actions** to ensure workflows are enabled
- Verify all 5 secrets are set in **Settings → Secrets and variables → Actions**
- Click "Run workflow" manually to test

**No bets placed?**
- Run `python -m bot.simulate_bets` locally and check stdout
- Verify The Odds API key is correct and has remaining quota
- Check that Supabase URL and service key are valid
- Review `bot/fetch_odds.py` for any API changes

**Telegram messages not arriving?**
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct
- Test locally: `python -m bot.notify --morning`
- Ensure the bot has permission to message the chat

**Dashboard not loading?**
- Verify Vercel environment variables are set correctly
- Check browser console for errors
- Ensure Supabase anon key allows public read access to `bets` and `bankroll_history`

## License

MIT

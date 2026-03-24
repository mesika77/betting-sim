import { neon } from '@neondatabase/serverless'

// Server-side only — DATABASE_URL is never exposed to the browser
// Lazy initialization so build doesn't fail without DATABASE_URL
export function getSql() {
  return neon(process.env.DATABASE_URL!)
}

// TypeScript types (keep the same as before)
export interface Bet {
  id: string
  date: string
  sport: string
  event_name: string
  market: string
  selection: string
  decimal_odds: number
  implied_prob: number
  stake: number
  result: 'pending' | 'won' | 'lost' | 'void'
  profit_loss: number | null
  commence_time: string | null
  created_at: string
}

export interface BankrollHistory {
  id: string
  date: string
  opening_balance: number
  closing_balance: number
  daily_pl: number
  total_pl: number
  num_bets: number
  num_won: number
  num_lost: number
}

export interface DailySummary {
  date: string
  bankroll: number
  daily_pl: number
  win_rate: number
  num_bets: number
}

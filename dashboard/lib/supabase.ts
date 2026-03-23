import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// TypeScript types for our tables
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

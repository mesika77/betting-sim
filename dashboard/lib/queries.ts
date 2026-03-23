import { supabase, Bet, BankrollHistory } from './supabase'

export async function getAllBets(): Promise<Bet[]> {
  const { data, error } = await supabase
    .from('bets')
    .select('*')
    .order('date', { ascending: false })
  if (error) throw error
  return data ?? []
}

export async function getTodayBets(): Promise<Bet[]> {
  const today = new Date().toISOString().split('T')[0]
  const { data, error } = await supabase
    .from('bets')
    .select('*')
    .eq('date', today)
    .order('implied_prob', { ascending: false })
  if (error) throw error
  return data ?? []
}

export async function getBankrollHistory(): Promise<BankrollHistory[]> {
  const { data, error } = await supabase
    .from('bankroll_history')
    .select('*')
    .order('date', { ascending: true })
  if (error) throw error
  return data ?? []
}

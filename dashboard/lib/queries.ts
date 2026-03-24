import { sql, Bet, BankrollHistory } from './db'

export async function getAllBets(): Promise<Bet[]> {
  const rows = await sql`SELECT * FROM bets ORDER BY date DESC, implied_prob DESC`
  return rows as Bet[]
}

export async function getTodayBets(): Promise<Bet[]> {
  const today = new Date().toISOString().split('T')[0]
  const rows = await sql`
    SELECT * FROM bets
    WHERE date = ${today}
    ORDER BY implied_prob DESC
  `
  return rows as Bet[]
}

export async function getBankrollHistory(): Promise<BankrollHistory[]> {
  const rows = await sql`SELECT * FROM bankroll_history ORDER BY date ASC`
  return rows as BankrollHistory[]
}

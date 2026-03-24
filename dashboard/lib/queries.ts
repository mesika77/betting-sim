import { getSql, Bet, BankrollHistory } from './db'

function toDateStr(val: unknown): string {
  if (val instanceof Date) return val.toISOString().split('T')[0]
  return String(val)
}

function parseBet(row: Record<string, unknown>): Bet {
  return {
    ...row,
    date: toDateStr(row.date),
    commence_time: row.commence_time
      ? new Date(row.commence_time as string).toLocaleString('en-GB', {
          timeZone: 'Asia/Jerusalem',
          hour: '2-digit',
          minute: '2-digit',
          day: '2-digit',
          month: '2-digit',
        })
      : null,
    decimal_odds: Number(row.decimal_odds),
    implied_prob: Number(row.implied_prob),
    stake: Number(row.stake),
    profit_loss: row.profit_loss != null ? Number(row.profit_loss) : null,
  } as Bet
}

function parseBankrollHistory(row: Record<string, unknown>): BankrollHistory {
  return {
    ...row,
    date: toDateStr(row.date),
    opening_balance: Number(row.opening_balance),
    closing_balance: Number(row.closing_balance),
    daily_pl: Number(row.daily_pl),
    total_pl: Number(row.total_pl),
    num_bets: Number(row.num_bets),
    num_won: Number(row.num_won),
    num_lost: Number(row.num_lost),
  } as BankrollHistory
}

export async function getAllBets(): Promise<Bet[]> {
  const sql = getSql()
  const rows = await sql`SELECT * FROM bets ORDER BY date DESC, implied_prob DESC`
  return rows.map(parseBet)
}

export async function getTodayBets(): Promise<Bet[]> {
  const sql = getSql()
  const today = new Date().toISOString().split('T')[0]
  const rows = await sql`
    SELECT * FROM bets
    WHERE date = ${today}
    ORDER BY implied_prob DESC
  `
  return rows.map(parseBet)
}

export async function getBankrollHistory(): Promise<BankrollHistory[]> {
  const sql = getSql()
  const rows = await sql`SELECT * FROM bankroll_history ORDER BY date ASC`
  return rows.map(parseBankrollHistory)
}

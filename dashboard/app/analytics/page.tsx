import { getAllBets, getBankrollHistory } from '@/lib/queries'
import { KpiCard } from '@/components/KpiCard'
import { Bet } from '@/lib/db'

interface SportStats {
  sport: string
  bets: number
  won: number
  winRate: number
}

function groupBySport(bets: Bet[]): SportStats[] {
  const map = new Map<string, { bets: number; won: number }>()

  for (const bet of bets) {
    if (bet.result === 'void' || bet.result === 'pending') continue
    const existing = map.get(bet.sport) ?? { bets: 0, won: 0 }
    map.set(bet.sport, {
      bets: existing.bets + 1,
      won: existing.won + (bet.result === 'won' ? 1 : 0),
    })
  }

  return Array.from(map.entries())
    .map(([sport, stats]) => ({
      sport,
      bets: stats.bets,
      won: stats.won,
      winRate: stats.won / Math.max(stats.bets, 1),
    }))
    .sort((a, b) => b.bets - a.bets)
}

export default async function AnalyticsPage() {
  const [bets, history] = await Promise.all([getAllBets(), getBankrollHistory()])

  const settledBets = bets.filter((b) => b.result === 'won' || b.result === 'lost')
  const sportStats = groupBySport(bets)

  const avgOdds =
    settledBets.length > 0
      ? settledBets.reduce((sum, b) => sum + b.decimal_odds, 0) / settledBets.length
      : 0

  const avgImpliedProb =
    settledBets.length > 0
      ? settledBets.reduce((sum, b) => sum + b.implied_prob, 0) / settledBets.length
      : 0

  const totalStaked = settledBets.reduce((sum, b) => sum + b.stake, 0)
  const totalPL = settledBets.reduce((sum, b) => sum + (b.profit_loss ?? 0), 0)
  const roi = totalStaked > 0 ? (totalPL / totalStaked) * 100 : 0

  const totalWon = settledBets.filter((b) => b.result === 'won').length
  const overallWinRate = totalWon / Math.max(settledBets.length, 1)

  const latest = history.length > 0 ? history[history.length - 1] : null

  function formatCurrency(val: number, showSign = false) {
    const abs = Math.abs(val).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    if (!showSign) return `$${abs}`
    return val >= 0 ? `+$${abs}` : `-$${abs}`
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
        <p className="text-sm text-gray-500 mt-1">Performance breakdown and statistics</p>
      </div>

      {/* Overall Performance */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Overall Performance</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <KpiCard
            label="Overall Win Rate"
            value={`${(overallWinRate * 100).toFixed(1)}%`}
            subtitle={`${totalWon}W / ${settledBets.length - totalWon}L`}
            positive={overallWinRate >= 0.5 ? true : overallWinRate > 0 ? false : undefined}
          />
          <KpiCard
            label="ROI"
            value={`${roi >= 0 ? '+' : ''}${roi.toFixed(2)}%`}
            positive={roi > 0 ? true : roi < 0 ? false : undefined}
          />
          <KpiCard
            label="Total Staked"
            value={formatCurrency(totalStaked)}
          />
          <KpiCard
            label="Net P&L"
            value={formatCurrency(totalPL, true)}
            positive={totalPL > 0 ? true : totalPL < 0 ? false : undefined}
          />
        </div>
      </div>

      {/* Odds Stats */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Odds &amp; Probability</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <KpiCard
            label="Avg Decimal Odds"
            value={avgOdds > 0 ? avgOdds.toFixed(3) : '—'}
            subtitle="across settled bets"
          />
          <KpiCard
            label="Avg Implied Prob"
            value={avgImpliedProb > 0 ? `${(avgImpliedProb * 100).toFixed(1)}%` : '—'}
            subtitle="model probability"
          />
          <KpiCard
            label="Settled Bets"
            value={String(settledBets.length)}
          />
          <KpiCard
            label="Current Bankroll"
            value={latest ? formatCurrency(latest.closing_balance) : '$5,000'}
          />
        </div>
      </div>

      {/* Win Rate by Sport */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Win Rate by Sport</h2>
        {sportStats.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm p-8 text-center text-gray-400">
            No settled bets yet.
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <th className="px-6 py-4">Sport</th>
                  <th className="px-6 py-4 text-right">Bets</th>
                  <th className="px-6 py-4 text-right">Won</th>
                  <th className="px-6 py-4 text-right">Win Rate</th>
                </tr>
              </thead>
              <tbody>
                {sportStats.map((row, i) => (
                  <tr
                    key={row.sport}
                    className={`border-b border-gray-50 hover:bg-blue-50 transition-colors ${
                      i % 2 === 0 ? 'bg-white' : 'bg-gray-50'
                    }`}
                  >
                    <td className="px-6 py-4 font-medium text-gray-800">{row.sport}</td>
                    <td className="px-6 py-4 text-right text-gray-600">{row.bets}</td>
                    <td className="px-6 py-4 text-right text-gray-600">{row.won}</td>
                    <td className="px-6 py-4 text-right">
                      <span
                        className={`font-semibold ${
                          row.winRate >= 0.5 ? 'text-green-600' : 'text-red-600'
                        }`}
                      >
                        {(row.winRate * 100).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

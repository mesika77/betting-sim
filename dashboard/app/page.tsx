import { getBankrollHistory, getTodayBets } from '@/lib/queries'
import { KpiCard } from '@/components/KpiCard'
import { BankrollChart } from '@/components/BankrollChart'
import { BetsTable } from '@/components/BetsTable'

export default async function OverviewPage() {
  const [history, todayBets] = await Promise.all([
    getBankrollHistory(),
    getTodayBets(),
  ])

  // Calculate KPIs
  const latest = history.length > 0 ? history[history.length - 1] : null

  const currentBankroll = latest?.closing_balance ?? 5000
  const totalPL = latest?.total_pl ?? 0

  const totalWon = history.reduce((sum, r) => sum + r.num_won, 0)
  const totalLost = history.reduce((sum, r) => sum + r.num_lost, 0)
  const winRate = totalWon / Math.max(totalWon + totalLost, 1)

  const daysRunning = history.length

  const dailyPLs = history.map((r) => r.daily_pl)
  const bestDay = dailyPLs.length > 0 ? Math.max(...dailyPLs) : 0
  const worstDay = dailyPLs.length > 0 ? Math.min(...dailyPLs) : 0

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
        <h1 className="text-2xl font-bold text-gray-900">Overview</h1>
        <p className="text-sm text-gray-500 mt-1">Simulated betting performance dashboard</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <KpiCard
          label="Current Bankroll"
          value={formatCurrency(currentBankroll)}
        />
        <KpiCard
          label="Total P&L"
          value={formatCurrency(totalPL, true)}
          positive={totalPL > 0 ? true : totalPL < 0 ? false : undefined}
        />
        <KpiCard
          label="Win Rate"
          value={`${(winRate * 100).toFixed(1)}%`}
          subtitle={`${totalWon}W / ${totalLost}L`}
          positive={winRate >= 0.5 ? true : winRate > 0 ? false : undefined}
        />
        <KpiCard
          label="Days Running"
          value={String(daysRunning)}
        />
        <KpiCard
          label="Best Day"
          value={formatCurrency(bestDay, true)}
          positive={bestDay > 0 ? true : undefined}
        />
        <KpiCard
          label="Worst Day"
          value={formatCurrency(worstDay, true)}
          positive={worstDay >= 0 ? true : false}
        />
      </div>

      {/* Bankroll Chart */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Bankroll Over Time</h2>
        {history.length > 0 ? (
          <BankrollChart data={history} />
        ) : (
          <div className="h-[300px] flex items-center justify-center text-gray-400">
            No history data yet.
          </div>
        )}
      </div>

      {/* Today's Bets */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Today&apos;s Bets
          {todayBets.length > 0 && (
            <span className="ml-2 text-sm font-normal text-gray-400">
              ({todayBets.length} bet{todayBets.length !== 1 ? 's' : ''})
            </span>
          )}
        </h2>
        <BetsTable bets={todayBets} showDate={false} />
      </div>
    </div>
  )
}

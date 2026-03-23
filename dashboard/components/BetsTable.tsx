'use client'
import { Bet } from '@/lib/supabase'

interface Props {
  bets: Bet[]
  showDate?: boolean
}

const resultStyles: Record<string, string> = {
  won: 'bg-green-100 text-green-800',
  lost: 'bg-red-100 text-red-800',
  pending: 'bg-yellow-100 text-yellow-800',
  void: 'bg-gray-100 text-gray-700',
}

export function BetsTable({ bets, showDate }: Props) {
  if (bets.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-8 text-center text-gray-400">
        No bets found.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl shadow-sm">
      <table className="min-w-full bg-white text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
            {showDate && <th className="px-4 py-3">Date</th>}
            <th className="px-4 py-3">Sport</th>
            <th className="px-4 py-3">Event</th>
            <th className="px-4 py-3">Market</th>
            <th className="px-4 py-3">Selection</th>
            <th className="px-4 py-3 text-right">Odds</th>
            <th className="px-4 py-3 text-right">Stake</th>
            <th className="px-4 py-3 text-center">Result</th>
            <th className="px-4 py-3 text-right">P&amp;L</th>
          </tr>
        </thead>
        <tbody>
          {bets.map((bet, i) => {
            const isEven = i % 2 === 0
            const pl = bet.profit_loss
            const plColor =
              pl == null ? 'text-gray-400' : pl >= 0 ? 'text-green-600' : 'text-red-600'
            const plText =
              pl == null
                ? '—'
                : pl >= 0
                ? `+$${pl.toFixed(2)}`
                : `-$${Math.abs(pl).toFixed(2)}`

            return (
              <tr
                key={bet.id}
                className={`border-b border-gray-50 hover:bg-blue-50 transition-colors ${
                  isEven ? 'bg-white' : 'bg-gray-50'
                }`}
              >
                {showDate && (
                  <td className="px-4 py-3 whitespace-nowrap text-gray-600">{bet.date}</td>
                )}
                <td className="px-4 py-3 whitespace-nowrap font-medium text-gray-700">
                  {bet.sport}
                </td>
                <td className="px-4 py-3 text-gray-700 max-w-xs truncate">{bet.event_name}</td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{bet.market}</td>
                <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{bet.selection}</td>
                <td className="px-4 py-3 text-right font-mono text-gray-700">
                  {bet.decimal_odds.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-gray-700">
                  ${bet.stake.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${
                      resultStyles[bet.result] ?? 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {bet.result}
                  </span>
                </td>
                <td className={`px-4 py-3 text-right font-mono font-semibold ${plColor}`}>
                  {plText}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

import { getAllBets } from '@/lib/queries'
import { BetsTable } from '@/components/BetsTable'

export default async function HistoryPage() {
  const bets = await getAllBets()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Bet History</h1>
        <p className="text-sm text-gray-500 mt-1">
          {bets.length} total bet{bets.length !== 1 ? 's' : ''} recorded
        </p>
      </div>

      <BetsTable bets={bets} showDate={true} />
    </div>
  )
}

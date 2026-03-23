'use client'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { BankrollHistory } from '@/lib/supabase'

interface Props {
  data: BankrollHistory[]
}

function formatCurrency(value: number) {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

export function BankrollChart({ data }: Props) {
  const chartData = data.map((row) => ({
    date: row.date,
    bankroll: row.closing_balance,
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 12, fill: '#6b7280' }}
          tickFormatter={(val: string) => {
            const d = new Date(val)
            return `${d.getMonth() + 1}/${d.getDate()}`
          }}
        />
        <YAxis
          tick={{ fontSize: 12, fill: '#6b7280' }}
          tickFormatter={(val: number) => formatCurrency(val)}
          width={80}
        />
        <Tooltip
          formatter={(value: number) => [formatCurrency(value), 'Bankroll']}
          labelFormatter={(label: string) => `Date: ${label}`}
          contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }}
        />
        <Line
          type="monotone"
          dataKey="bankroll"
          stroke="#2563eb"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

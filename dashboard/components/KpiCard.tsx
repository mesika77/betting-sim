interface KpiCardProps {
  label: string
  value: string
  subtitle?: string
  positive?: boolean
}

export function KpiCard({ label, value, subtitle, positive }: KpiCardProps) {
  const valueColor =
    positive === true
      ? 'text-green-600'
      : positive === false
      ? 'text-red-600'
      : 'text-gray-900'

  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${valueColor}`}>{value}</p>
      {subtitle && (
        <p className="text-sm text-gray-400 mt-1">{subtitle}</p>
      )}
    </div>
  )
}

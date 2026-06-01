import { Card } from "./ui/card"

interface StatCardProps {
  label: string
  value: string | number | null | undefined
  subtext?: string
  accent?: boolean
  accentColor?: 'vyper' | 'green' | 'red' | 'yellow' | 'blue'
  trend?: string
  trendDirection?: 'up' | 'down'
}

const accentMap: Record<string, string> = {
  vyper: 'text-vyper-400',
  green: 'text-green-400',
  red: 'text-red-400',
  yellow: 'text-yellow-400',
  blue: 'text-blue-400',
}

export function StatCard({ label, value, subtext, accent, accentColor = 'vyper', trend, trendDirection }: StatCardProps) {
  return (
    <Card>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm dark:text-[#68687a] light:text-[#71717a]">{label}</span>
        {trend && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            trendDirection === 'up'
              ? 'bg-green-500/10 text-green-400'
              : trendDirection === 'down'
              ? 'bg-red-500/10 text-red-400'
              : 'bg-vyper-500/10 text-vyper-400'
          }`}>
            {trend}
          </span>
        )}
      </div>
      <div className={`text-3xl font-bold ${accent ? accentMap[accentColor] : 'dark:text-[#d4d4dc] light:text-[#09090b]'}`}>
        {value ?? '—'}
      </div>
      {subtext && (
        <div className="text-xs dark:text-[#68687a] light:text-[#71717a] mt-1">{subtext}</div>
      )}
    </Card>
  )
}

import React from 'react'

interface ScoreCardProps {
  title: string
  score: number | null
  subtitle?: string
  icon?: string
  delayMs?: number
  tooltip?: string
}

export const ScoreCard: React.FC<ScoreCardProps> = ({ title, score, subtitle, icon, delayMs = 0, tooltip }) => {
  const isNull = score === null
  const value = isNull ? 'N/A' : score

  let colorClass = 'text-zinc-400'
  let bgClass = 'bg-surface-strong'
  let barClass = 'bg-zinc-300'

  if (!isNull) {
    if (score < 40) {
      colorClass = 'text-red-600'
      bgClass = 'bg-red-50'
      barClass = 'bg-red-400'
    } else if (score < 70) {
      colorClass = 'text-amber-600'
      bgClass = 'bg-amber-50'
      barClass = 'bg-amber-400'
    } else {
      colorClass = 'text-emerald-600'
      bgClass = 'bg-emerald-50'
      barClass = 'bg-emerald-400'
    }
  }

  return (
    <div
      style={{ animationDelay: `${delayMs}ms` }}
      className={`group relative animate-card-in flex flex-col p-4 rounded-xl border border-edge transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:shadow-black/5 ${bgClass}`}
    >
      {/* Tooltip */}
      {tooltip && (
        <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 w-48 -translate-x-1/2 opacity-0 transition-all duration-200 group-hover:-translate-y-1 group-hover:opacity-100">
          <div className="rounded-lg border border-zinc-700/50 bg-zinc-800 px-3 py-2 text-center text-xs leading-relaxed text-zinc-100 shadow-xl">
            {tooltip}
            <div className="absolute left-1/2 top-full h-2 w-2 -translate-x-1/2 -translate-y-1/2 rotate-45 border-b border-r border-zinc-700/50 bg-zinc-800" />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-1">
        <div className="text-sm font-medium text-zinc-500">{title}</div>
        {icon && (
          <span
            aria-hidden="true"
            style={{ animationDelay: `${delayMs + 150}ms` }}
            className="animate-icon-pop text-lg leading-none transition-transform duration-200 group-hover:rotate-12 group-hover:scale-110"
          >
            {icon}
          </span>
        )}
      </div>
      <div className={`text-3xl font-bold tracking-tight ${colorClass}`}>{value}</div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface">
        <div
          className={`animate-bar-grow h-full rounded-full ${barClass}`}
          style={{ width: isNull ? '0%' : `${score}%` }}
        />
      </div>
      {subtitle && <div className="text-xs text-zinc-500 mt-2">{subtitle}</div>}
    </div>
  )
}

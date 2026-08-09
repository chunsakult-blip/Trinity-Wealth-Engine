import React from 'react'
import { parseDataQualityFlag, CATEGORY_CONFIG, type FlagCategory, type FormattedFlag } from '../../lib/dataQualityFlags'

interface DataQualityFlagsCardProps {
  flags: string[]
}

export const DataQualityFlagsCard: React.FC<DataQualityFlagsCardProps> = ({ flags }) => {
  if (!flags || flags.length === 0) return null

  const parsedFlags = flags.map(parseDataQualityFlag)

  // Group by category while preserving priority order
  const categoryOrder: FlagCategory[] = ['critical_fallback', 'model_methodology', 'market_warning', 'low_impact_fallback']
  const grouped = categoryOrder.reduce<Record<FlagCategory, FormattedFlag[]>>((acc, cat) => {
    acc[cat] = parsedFlags.filter((f) => f.category === cat)
    return acc
  }, { critical_fallback: [], model_methodology: [], market_warning: [], low_impact_fallback: [] })

  return (
    <div className="space-y-4">
      {categoryOrder.map((cat) => {
        const items = grouped[cat]
        if (items.length === 0) return null

        const cfg = CATEGORY_CONFIG[cat]

        return (
          <div key={cat} className={`rounded-xl border ${cfg.borderClass} ${cfg.containerBgClass} p-4 transition-all shadow-sm`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className={`inline-flex items-center justify-center p-1 rounded-lg ${cfg.iconBgClass} ${cfg.iconColorClass}`}>
                  {cat === 'critical_fallback' ? (
                    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  ) : cat === 'model_methodology' ? (
                    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                    </svg>
                  ) : cat === 'market_warning' ? (
                    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                    </svg>
                  )}
                </span>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-700">{cfg.title}</h4>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${cfg.badgeBg} ${cfg.badgeTextClass}`}>
                {cfg.badgeText} ({items.length})
              </span>
            </div>

            <div className="space-y-2 mt-2">
              {items.map((item, idx) => (
                <div key={idx} className="flex flex-col text-sm border-l-2 border-zinc-300 pl-3 py-0.5" title={item.rawCode}>
                  <div className="flex items-center gap-2 font-medium text-zinc-800">
                    <span>{item.label}</span>
                  </div>
                  {item.subtext && <p className="text-xs text-zinc-500 mt-0.5 leading-relaxed">{item.subtext}</p>}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

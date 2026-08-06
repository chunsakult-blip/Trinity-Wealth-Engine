import React, { useState } from 'react'
import type { EquityDetailDTO } from '../../api/types'
import { ScoreCard } from './ScoreCard'
import ScoreRing from './ScoreRing'
import { sentimentClass } from '../../lib/sentiment'
import { EquityNews } from './EquityNews'
import { EquityNotesTab } from './EquityNotesTab'

interface EquityDetailProps {
  status: 'loading' | 'error' | 'not-found' | 'success' | 'idle'
  data?: EquityDetailDTO
  errorMessage?: string
}

const eyebrowClass = 'text-xs font-semibold uppercase tracking-wider text-sky-600'

const QUANT_STAGGER_STEP_MS = 60

export const EquityDetail: React.FC<EquityDetailProps> = ({ status, data, errorMessage }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'news' | 'notes'>('overview')

  if (status === 'idle') {
    return null
  }

  if (status === 'loading') {
    return (
      <div className="flex justify-center items-center h-64 text-zinc-500" aria-live="polite">
        กำลังโหลดข้อมูล...
      </div>
    )
  }

  if (status === 'not-found') {
    return (
      <div className="flex flex-col justify-center items-center h-64 bg-surface rounded-xl border border-dashed border-edge p-8 text-center">
        <svg className="w-12 h-12 text-zinc-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <h3 className="text-lg font-medium text-zinc-900 mb-1">ไม่พบข้อมูล</h3>
        <p className="text-zinc-500 max-w-sm">
          ยังไม่มีการวิเคราะห์สำหรับหุ้นตัวนี้ กรุณาสั่งงานผ่านผู้จัดการ (Manager Agent) เพื่อเริ่มต้นการวิเคราะห์
        </p>
      </div>
    )
  }

  if (status === 'error' || !data) {
    return (
      <div className="flex flex-col justify-center items-center h-64 bg-red-50 rounded-xl border border-red-200 p-8 text-center text-red-600" role="alert">
        <h3 className="text-lg font-medium mb-1">เกิดข้อผิดพลาด</h3>
        <p>{errorMessage || 'ไม่สามารถโหลดข้อมูลได้'}</p>
      </div>
    )
  }

  return (
    <div className="animate-page-in space-y-8">
      {/* Masthead */}
      <div className="flex flex-col gap-4 border-b border-edge pb-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className={eyebrowClass}>Equity Report</div>
          <h2 className="font-serif text-4xl font-semibold tracking-tight text-zinc-900">
            {data.ticker} <span className="text-zinc-500 font-normal text-lg">({data.market})</span>
          </h2>
          {data.company_name && <p className="text-zinc-500">{data.company_name}</p>}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className={`px-2.5 py-0.5 rounded-full border text-xs font-medium uppercase tracking-wider ${sentimentClass(data.market_sentiment)}`}>
              {data.market_sentiment}
            </span>
            <span className="text-xs text-zinc-400">
              อัปเดต {new Date(data.evaluated_at).toLocaleString('th-TH')}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 self-start rounded-2xl border border-edge bg-panel px-5 py-4 shadow-sm shadow-black/5">
          <ScoreRing score={data.composite_score} />
          <div>
            <div className="text-sm font-semibold text-zinc-700">Composite</div>
            <div className="text-xs text-zinc-400">Quant Score</div>
          </div>
        </div>
      </div>

      {/* Sub-nav Tab Switcher */}
      <div className="flex border-b border-edge gap-6 text-sm font-medium">
        <button
          onClick={() => setActiveTab('overview')}
          className={`pb-3 border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'overview'
              ? 'border-sky-600 text-sky-600 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-900'
          }`}
        >
          <span>📊 Overview</span>
        </button>
        <button
          onClick={() => setActiveTab('news')}
          className={`pb-3 border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'news'
              ? 'border-sky-600 text-sky-600 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-900'
          }`}
        >
          <span>📰 News</span>
        </button>
        <button
          onClick={() => setActiveTab('notes')}
          className={`pb-3 border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'notes'
              ? 'border-sky-600 text-sky-600 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-900'
          }`}
        >
          <span>📓 Notes</span>
        </button>
      </div>

      {activeTab === 'news' ? (
        <EquityNews ticker={data.ticker} />
      ) : activeTab === 'notes' ? (
        <EquityNotesTab ticker={data.ticker} />
      ) : (

        <>
          {data.data_quality_flags && data.data_quality_flags.length > 0 && (
            <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-xl">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-amber-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-amber-800">Data Quality Flags</h3>
                  <div className="mt-2 text-sm text-amber-700">
                    <ul className="list-disc pl-5 space-y-1">
                      {data.data_quality_flags.map((flag, idx) => (
                        <li key={idx}>{flag}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Secondary quant score rail (Composite lives in the masthead ring above) */}
          <div className="flex flex-wrap gap-4">
            {[
              { title: 'Value', icon: '💰', score: data.quant_signals.value_score, tooltip: 'ประเมินความถูกแพงของหุ้นเทียบกับปัจจัยพื้นฐาน เช่น P/E, P/BV' },
              { title: 'Growth', icon: '🌱', score: data.quant_signals.growth_score, tooltip: 'ประเมินแนวโน้มการเติบโตของรายได้และกำไรทั้งในอดีตและอนาคต' },
              { title: 'Quality', icon: '💎', score: data.quant_signals.quality_score, tooltip: 'ประเมินคุณภาพของกิจการ เช่น อัตราการทำกำไร และผลตอบแทนต่อส่วนผู้ถือหุ้น (ROE)' },
              { title: 'Momentum', icon: '🚀', score: data.quant_signals.momentum_score, tooltip: 'ประเมินความแข็งแกร่งของแนวโน้มราคาหุ้นในช่วงที่ผ่านมา' },
              { title: 'Dividend', icon: '🪙', score: data.quant_signals.dividend_score, tooltip: 'ประเมินความน่าสนใจของเงินปันผล ทั้งอัตราผลตอบแทนและความสม่ำเสมอ' },
              { title: 'Solvency', icon: '🛡️', score: data.quant_signals.solvency_score, tooltip: 'ประเมินความมั่นคงทางการเงิน ความสามารถในการชำระหนี้ และสภาพคล่อง' },
            ].map((m, i) => (
              <ScoreCard key={m.title} title={m.title} icon={m.icon} score={m.score} tooltip={m.tooltip} delayMs={i * QUANT_STAGGER_STEP_MS} />
            ))}
          </div>

          {/* Editorial reading grid: main narrative (7/12) + sentiment rail (5/12) */}
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
            <div className="space-y-8 lg:col-span-7">
              <section>
                <h3 className={eyebrowClass}>Base Case Summary</h3>
                <p className="mt-3 max-w-prose text-[15px] leading-7 text-zinc-700 whitespace-pre-line">{data.base_case_summary}</p>
              </section>

              <section>
                <h3 className={eyebrowClass}>Narrative Analysis</h3>
                <p className="mt-3 max-w-prose text-[15px] leading-7 text-zinc-700 whitespace-pre-line">{data.narrative_analysis}</p>
              </section>
            </div>

            <div className="lg:col-span-5">
              <div className="space-y-4 rounded-xl border border-edge bg-panel p-5 shadow-sm shadow-black/5">
                <h3 className={eyebrowClass}>Sentiment Context</h3>

                {data.sentiment_context.key_themes && data.sentiment_context.key_themes.length > 0 && (
                  <div>
                    <span className="text-xs font-medium text-zinc-500 block mb-1.5">Key Themes</span>
                    <div className="flex flex-wrap gap-1.5">
                      {data.sentiment_context.key_themes.map((t, i) => (
                        <span key={i} className="rounded-full border border-edge bg-surface-strong px-2.5 py-0.5 text-xs font-medium text-zinc-700">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {data.sentiment_context.tail_risks && data.sentiment_context.tail_risks.length > 0 && (
                  <div className="rounded-lg border-l-4 border-red-300 bg-red-50/70 p-3">
                    <span className="text-xs font-semibold text-red-800 block mb-1">Tail Risks</span>
                    <ul className="list-disc pl-4 text-sm text-red-700 space-y-0.5">
                      {data.sentiment_context.tail_risks.map((t, i) => <li key={i}>{t}</li>)}
                    </ul>
                  </div>
                )}

                <div>
                  <span className="text-xs font-medium text-zinc-500 block mb-1">Sources Summary</span>
                  <p className="text-zinc-600 text-sm whitespace-pre-line">{data.sentiment_context.sources_summary}</p>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      <div className="border-t border-edge pt-4 text-xs text-zinc-400 flex flex-wrap gap-x-4">
        <div>Source: {data.source_file}</div>
        <div>Generated by: {data.generated_by}</div>
      </div>
    </div>
  )
}

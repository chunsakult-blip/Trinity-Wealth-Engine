import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { EquitySummaryDTO, EquityDetailDTO } from '../api/types'
import { EquityDetail } from '../components/equity/EquityDetail'
import { sentimentClass } from '../lib/sentiment'
import TextInput from '../components/ui/TextInput'
import ScoreRing from '../components/equity/ScoreRing'

// For explicit mock mode
const isMockMode = import.meta.env.VITE_EQUITY_MOCK === 'true' && import.meta.env.DEV

const STAGGER_STEP_MS = 30
const STAGGER_CAP_MS = 240

export default function Equity() {
  const { ticker } = useParams<{ ticker?: string }>()
  const navigate = useNavigate()

  const [summaries, setSummaries] = useState<EquitySummaryDTO[]>([])
  const [loadingList, setLoadingList] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState<'ticker' | 'score_desc'>('ticker')

  const [detailData, setDetailData] = useState<EquityDetailDTO | undefined>(undefined)
  const [detailStatus, setDetailStatus] = useState<'idle' | 'loading' | 'success' | 'error' | 'not-found'>('idle')
  const [detailError, setDetailError] = useState<string | undefined>(undefined)

  useEffect(() => {
    const fetchList = async () => {
      try {
        setLoadingList(true)
        if (isMockMode) {
          const { mockEquitySummary } = await import('../mocks/equity')
          setSummaries(mockEquitySummary)
        } else {
          const data = await api.getEquityLatest()
          setSummaries(data)
        }
        setListError(null)
      } catch (err: any) {
        console.error('Failed to fetch equity list:', err)
        setListError(err.message || 'Failed to load list')
      } finally {
        setLoadingList(false)
      }
    }
    fetchList()
  }, [])

  useEffect(() => {
    const fetchDetail = async () => {
      if (!ticker) {
        setDetailStatus('idle')
        setDetailData(undefined)
        return
      }

      try {
        setDetailStatus('loading')
        if (isMockMode) {
          const { mockEquityDetailAAPL } = await import('../mocks/equity')
          if (ticker.toUpperCase() === 'AAPL') {
            setDetailData(mockEquityDetailAAPL)
            setDetailStatus('success')
          } else {
            setDetailStatus('not-found')
          }
        } else {
          const data = await api.getEquityDetail(ticker)
          setDetailData(data)
          setDetailStatus('success')
        }
      } catch (err: any) {
        console.error('Failed to fetch equity detail:', err)
        if (err.status === 404) {
          setDetailStatus('not-found')
        } else {
          setDetailStatus('error')
          setDetailError(err.message || 'Error loading detail')
        }
      }
    }

    fetchDetail()
  }, [ticker])

  const filteredSummaries = [...summaries]
    .filter(item =>
      item.ticker.toLowerCase().includes(searchQuery.trim().toLowerCase())
    )
    .sort((a, b) => {
      if (sortBy === 'score_desc') {
        const scoreA = a.composite_score ?? -1
        const scoreB = b.composite_score ?? -1
        return scoreB - scoreA
      }
      return a.ticker.localeCompare(b.ticker)
    })

  return (
    <div className="animate-page-in flex h-[calc(100vh-4rem)] flex-col md:flex-row">
      {/* Sidebar List */}
      <div className={`w-full md:w-1/3 md:min-w-[300px] md:max-w-[400px] border-r border-edge overflow-y-auto bg-surface p-4 ${ticker ? 'hidden md:block' : 'block'}`}>
        <h2 className="text-xl font-bold mb-4 text-zinc-900">
          Equity Analysis
          {isMockMode && <span className="ml-2 text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">MOCK</span>}
        </h2>

        <div className="mb-4 space-y-3">
          <TextInput
            placeholder="ค้นหาหุ้น (เช่น AAPL)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full"
          />
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-500 whitespace-nowrap">เรียงตาม:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'ticker' | 'score_desc')}
              className="w-full rounded-lg border border-edge bg-surface px-3 py-1.5 text-sm text-zinc-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              <option value="ticker">ชื่อหุ้น (A-Z)</option>
              <option value="score_desc">คะแนน (มากไปน้อย)</option>
            </select>
          </div>
        </div>

        {loadingList ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="animate-shimmer h-16 rounded-lg border border-edge" />
            ))}
          </div>
        ) : listError ? (
          <div className="text-sm text-red-500">{listError}</div>
        ) : filteredSummaries.length === 0 ? (
          <div className="text-sm text-zinc-500 text-center py-4 bg-surface-strong border border-edge rounded-lg">ไม่พบข้อมูลหุ้นที่ค้นหา</div>
        ) : (
          <ul className="space-y-2">
            {filteredSummaries.map((item, i) => (
              <li key={item.ticker}>
                <button
                  onClick={() => navigate(`/equity/${item.ticker.toLowerCase()}`)}
                  style={{ animationDelay: `${Math.min(i * STAGGER_STEP_MS, STAGGER_CAP_MS)}ms` }}
                  className={`animate-card-in w-full text-left p-3 rounded-lg border transition-colors flex items-center gap-3 ${
                    ticker?.toUpperCase() === item.ticker.toUpperCase()
                      ? 'bg-panel border-sky-200 shadow-[0_8px_24px_rgba(14,165,233,0.08)]'
                      : 'bg-panel/50 border-transparent hover:border-edge hover:bg-surface-strong'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-semibold text-zinc-900 truncate">{item.ticker}</span>
                      <span className="text-xs text-zinc-500 shrink-0 ml-2">{new Date(item.evaluated_at).toLocaleDateString()}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-zinc-500">{item.market}</span>
                      <span className={`px-2 py-0.5 rounded-full border text-xs whitespace-nowrap ${sentimentClass(item.market_sentiment)}`}>
                        {item.market_sentiment}
                      </span>
                    </div>
                  </div>
                  <div className="shrink-0 flex items-center justify-center">
                    <ScoreRing score={item.composite_score} size={44} textSizeClass="text-sm" />
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Main Detail Area */}
      <div className={`flex-1 overflow-y-auto p-4 md:p-8 ${!ticker ? 'hidden md:block' : 'block'}`}>
        {!ticker ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-400 gap-3">
            <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span className="text-sm">เลือกหุ้นจากรายการด้านซ้ายเพื่อดูรายละเอียด</span>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto">
            <div className="md:hidden mb-4">
              <button
                onClick={() => navigate('/equity')}
                className="flex items-center text-sm text-sky-600 hover:text-sky-800"
              >
                <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                กลับไปหน้ารายการ
              </button>
            </div>
            <EquityDetail status={detailStatus} data={detailData} errorMessage={detailError} />
          </div>
        )}
      </div>
    </div>
  )
}

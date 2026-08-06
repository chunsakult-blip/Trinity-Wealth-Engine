import type { EquitySummaryDTO, EquityDetailDTO, QuantSignalsDTO } from '../api/types'

export const mockEquitySummary: EquitySummaryDTO[] = [
  {
    ticker: 'AAPL',
    market: 'US',
    company_name: 'Apple Inc.',
    analysis_date: '2026-08-03',
    evaluated_at: '2026-08-03T10:00:00Z',
    market_sentiment: 'bullish',
    composite_score: 82.5,
    data_quality_flags: [],
    source_file: '30_Knowledge_Base/Stocks/AAPL/AAPL Equity Analysis 2026-08-03.md',
    sidecar_file: '30_Knowledge_Base/Stocks/AAPL/AAPL Equity Analysis 2026-08-03.json',
  },
  {
    ticker: 'PTT',
    market: 'TH',
    company_name: 'PTT PCL',
    analysis_date: '2026-08-03',
    evaluated_at: '2026-08-03T09:30:00Z',
    market_sentiment: 'neutral',
    composite_score: 55.0,
    data_quality_flags: ['missing_eps_q3'],
    source_file: '30_Knowledge_Base/Stocks/PTT/PTT Equity Analysis 2026-08-03.md',
    sidecar_file: '30_Knowledge_Base/Stocks/PTT/PTT Equity Analysis 2026-08-03.json',
  },
]

export const mockEquityDetailAAPL: EquityDetailDTO = {
  ...(mockEquitySummary[0] as EquitySummaryDTO),
  quant_signals: {
    ticker: 'AAPL',
    market: 'US',
    evaluated_at: '2026-08-03T10:00:00Z',
    composite_score: 82.5,
    value_score: 65,
    growth_score: 90,
    quality_score: 95,
    momentum_score: 80,
    volatility_pct: 20.5,
    beta: 1.15,
  } as QuantSignalsDTO,
  sentiment_context: {
    evaluated_at: '2026-08-03T10:00:00Z',
    market_sentiment: 'bullish',
    key_themes: ['AI Integration', 'Services Growth', 'Hardware Cycle'],
    tail_risks: ['Supply Chain Disruption', 'Regulatory Scrutiny'],
    sources_summary: 'Analyzed 15 recent earnings call transcripts and 5 analyst reports.',
    report_references: [],
  },
  narrative_analysis:
    'Apple is well-positioned to capitalize on the upcoming AI supercycle. The seamless integration of Apple Intelligence across iOS, iPadOS, and macOS will likely drive a massive upgrade cycle.',
  base_case_summary: 'Strong hardware cycle driven by AI features, supported by robust services revenue growth.',
  generated_by: 'equity_intel',
}


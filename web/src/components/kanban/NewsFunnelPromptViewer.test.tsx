import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import NewsFunnelPromptViewer from './NewsFunnelPromptViewer'
import { api } from '../../api/client'

vi.mock('../../api/client', () => ({
  api: {
    getNewsFunnelPending: vi.fn(),
    getNewsFunnelFiltered: vi.fn(),
  },
}))

describe('NewsFunnelPromptViewer', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders pending items and collapsible filtered items accordion', async () => {
    vi.mocked(api.getNewsFunnelPending).mockResolvedValue([
      {
        event_id: 'ev-pend-1',
        canonical_title: 'Pending High Impact Title',
        comprehensive_summary: 'Pending summary',
        macro_impact_score: 8,
        asset_impact_score: 7,
        extracted_tickers: ['NVDA'],
        extracted_themes: ['AI'],
        primary_tags: [],
        sources: ['Reuters'],
        links: ['http://example.com/pend'],
      },
    ])

    vi.mocked(api.getNewsFunnelFiltered).mockResolvedValue([
      {
        event_id: 'ev-err-1',
        canonical_title: 'Failed Paywall Article',
        comprehensive_summary: '',
        macro_impact_score: 8,
        asset_impact_score: 7,
        extracted_tickers: ['AAPL'],
        extracted_themes: [],
        primary_tags: [],
        sources: ['Bloomberg'],
        links: ['http://example.com/err'],
        status: 'skipped_error',
        error_msg: 'Paywalled content',
        ingested_at: '2026-07-17T05:00:00',
      },
      {
        event_id: 'ev-rej-1',
        canonical_title: 'Low Impact News Item',
        comprehensive_summary: 'Low summary',
        macro_impact_score: 5,
        asset_impact_score: 4,
        extracted_tickers: [],
        extracted_themes: [],
        primary_tags: [],
        sources: ['WSJ'],
        links: ['http://example.com/rej'],
        status: 'rejected',
        triage_reasoning: 'Score below threshold',
        ingested_at: '2026-07-17T04:00:00',
      },
    ])

    render(<NewsFunnelPromptViewer prompt="### News Funnel" />)

    // Verify pending item is displayed
    await waitFor(() => {
      expect(screen.getByText('Pending High Impact Title')).toBeInTheDocument()
    })

    // Verify accordion button is displayed with count (2)
    const accordionBtn = screen.getByText(/ข่าวที่ไม่ผ่านเกณฑ์หรือข้ามการบันทึก \(2 รายการ\)/)
    expect(accordionBtn).toBeInTheDocument()
    expect(screen.getByText('▼ แสดงรายการ')).toBeInTheDocument()

    // Accordion contents should not be visible before click
    expect(screen.queryByText('Failed Paywall Article')).not.toBeInTheDocument()

    // Click accordion to expand
    fireEvent.click(accordionBtn)

    await waitFor(() => {
      expect(screen.getByText('▲ ซ่อนรายการ')).toBeInTheDocument()
      expect(screen.getByText('Failed Paywall Article')).toBeInTheDocument()
      expect(screen.getByText('Low Impact News Item')).toBeInTheDocument()
      expect(screen.getByText('Skipped: ดึงข้อมูลไม่สำเร็จ')).toBeInTheDocument()
      expect(screen.getByText('Rejected: ไม่ผ่านคัดเลือก')).toBeInTheDocument()
      expect(screen.getByText(/Paywalled content/)).toBeInTheDocument()
      expect(screen.getByText(/Score below threshold/)).toBeInTheDocument()
    })
  })

  it('handles checkbox selection, toggle all, and dispatch button callback', async () => {
    vi.mocked(api.getNewsFunnelPending).mockResolvedValue([
      {
        event_id: 'ev-1',
        canonical_title: 'News 1',
        comprehensive_summary: 'Summary 1',
        macro_impact_score: 8,
        asset_impact_score: 7,
        extracted_tickers: [],
        extracted_themes: [],
        primary_tags: [],
        sources: [],
        links: [],
      },
      {
        event_id: 'ev-2',
        canonical_title: 'News 2',
        comprehensive_summary: 'Summary 2',
        macro_impact_score: 9,
        asset_impact_score: 8,
        extracted_tickers: [],
        extracted_themes: [],
        primary_tags: [],
        sources: [],
        links: [],
      },
    ])
    vi.mocked(api.getNewsFunnelFiltered).mockResolvedValue([])

    const onSelectionChange = vi.fn()
    const onDispatch = vi.fn()

    render(
      <NewsFunnelPromptViewer
        prompt="### News Funnel"
        onSelectionChange={onSelectionChange}
        onDispatch={onDispatch}
        isExecOrDone={false}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('News 1')).toBeInTheDocument()
    })

    // Selected by default
    expect(onSelectionChange).toHaveBeenCalledWith(['ev-1', 'ev-2'])

    // Deselect all button
    const toggleAllBtn = screen.getByText('ยกเลิกทั้งหมด')
    fireEvent.click(toggleAllBtn)
    expect(onSelectionChange).toHaveBeenLastCalledWith([])

    // Select all button
    const selectAllBtn = screen.getByText('เลือกทั้งหมด')
    fireEvent.click(selectAllBtn)
    expect(onSelectionChange).toHaveBeenLastCalledWith(['ev-1', 'ev-2'])

    // Dispatch button
    const dispatchBtn = screen.getByText(/🚀 เริ่มสังเคราะห์ \(2 รายการ\)/)
    fireEvent.click(dispatchBtn)
    expect(onDispatch).toHaveBeenCalledTimes(1)
  })
})

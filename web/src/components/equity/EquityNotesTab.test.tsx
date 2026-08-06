import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { EquityNotesTab } from './EquityNotesTab'
import { api } from '../../api/client'

vi.mock('../../api/client', () => ({
  api: {
    getEquityNotes: vi.fn(),
    getEquityNoteContent: vi.fn(),
  },
}))

describe('EquityNotesTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state initially', () => {
    vi.mocked(api.getEquityNotes).mockImplementation(() => new Promise(() => { }))
    render(<EquityNotesTab ticker="AAPL" />)
    expect(screen.getByText('กำลังโหลด Obsidian Notes...')).toBeInTheDocument()
  })

  it('renders error state on API failure', async () => {
    vi.mocked(api.getEquityNotes).mockRejectedValue(new Error('Network error loading notes'))
    render(<EquityNotesTab ticker="AAPL" />)

    await waitFor(() => {
      expect(screen.getByText('เกิดข้อผิดพลาด')).toBeInTheDocument()
      expect(screen.getByText('Network error loading notes')).toBeInTheDocument()
    })
  })

  it('renders empty state when no notes found', async () => {
    vi.mocked(api.getEquityNotes).mockResolvedValue({
      ticker: 'AAPL',
      total_count: 0,
      items: [],
    })

    render(<EquityNotesTab ticker="AAPL" />)

    await waitFor(() => {
      expect(screen.getByText('ไม่พบ Obsidian Notes สำหรับหุ้น AAPL')).toBeInTheDocument()
      expect(screen.getByText(/สามารถเพิ่มโน้ตเกี่ยวกับหุ้นตัวนี้ใน Obsidian Vault/)).toBeInTheDocument()
    })
  })

  it('renders note cards with correct matched_by badges and obsidian links', async () => {
    vi.mocked(api.getEquityNotes).mockResolvedValue({
      ticker: 'AAPL',
      total_count: 4,
      items: [
        {
          title: 'Watchlist Thesis (AAPL)',
          folder: 'WatchlistItems',
          relative_path: '20_Portfolio_Management/Current_Holdings/WatchlistItems/AAPL.md',
          obsidian_uri: 'obsidian://open?vault=Vault&file=WatchlistItems/AAPL.md',
          snippet: 'Watchlist snippet content',
          modified_at: '2026-08-05T12:00:00Z',
          matched_by: 'watchlist',
        },
        {
          title: 'AAPL Deep Dive',
          folder: 'Stocks/AAPL',
          relative_path: '30_Knowledge_Base/Stocks/AAPL/AAPL Deep Dive.md',
          obsidian_uri: 'obsidian://open?vault=Vault&file=Stocks/AAPL/AAPL Deep Dive.md',
          snippet: 'Stock note snippet',
          modified_at: '2026-08-04T10:00:00Z',
          matched_by: 'stock_note',
        },
        {
          title: 'Trading Journal [2026-08-03 14:00:00]',
          folder: 'Journals_and_Reports',
          relative_path: '20_Portfolio_Management/Journals_and_Reports/Trading_Journal.md',
          obsidian_uri: 'obsidian://open?vault=Vault&file=Trading_Journal.md',
          snippet: 'Journal entry snippet',
          modified_at: '2026-08-03T14:00:00Z',
          matched_by: 'journal',
        },
        {
          title: 'Custom Tag Note',
          folder: 'Other',
          relative_path: 'Other/Note.md',
          obsidian_uri: 'obsidian://open?vault=Vault&file=Other/Note.md',
          snippet: 'Custom tag snippet',
          modified_at: '2026-08-01T08:00:00Z',
          matched_by: 'tag',
        },
      ],
    })

    render(<EquityNotesTab ticker="AAPL" />)

    await waitFor(() => {
      expect(screen.getByText('Obsidian Notes (4)')).toBeInTheDocument()
      expect(screen.getByText('Watchlist Thesis (AAPL)')).toBeInTheDocument()
      expect(screen.getByText('AAPL Deep Dive')).toBeInTheDocument()
      expect(screen.getByText('Trading Journal [2026-08-03 14:00:00]')).toBeInTheDocument()

      // Badges
      expect(screen.getByText('📌 Watchlist')).toBeInTheDocument()
      expect(screen.getByText('📝 Stock Note')).toBeInTheDocument()
      expect(screen.getByText('📓 Trading Journal')).toBeInTheDocument()
      expect(screen.getByText('📄 tag')).toBeInTheDocument()
    })
  })

  it('opens preview modal when "ดูเนื้อหา" is clicked and closes it when "ปิด" is clicked', async () => {
    vi.mocked(api.getEquityNotes).mockResolvedValue({
      ticker: 'AAPL',
      total_count: 1,
      items: [
        {
          title: 'AAPL Deep Dive',
          folder: 'Stocks/AAPL',
          relative_path: '30_Knowledge_Base/Stocks/AAPL/AAPL Deep Dive.md',
          obsidian_uri: 'obsidian://open?vault=Vault&file=Stocks/AAPL/AAPL Deep Dive.md',
          snippet: 'Stock note snippet',
          modified_at: '2026-08-04T10:00:00Z',
          matched_by: 'stock_note',
        },
      ],
    })

    vi.mocked(api.getEquityNoteContent).mockResolvedValue({
      title: 'AAPL Deep Dive',
      relative_path: '30_Knowledge_Base/Stocks/AAPL/AAPL Deep Dive.md',
      content: '# AAPL Valuation Thesis\nFull content of the note.',
      modified_at: '2026-08-04T10:00:00Z',
    })

    render(<EquityNotesTab ticker="AAPL" />)

    await waitFor(() => {
      expect(screen.getByText('AAPL Deep Dive')).toBeInTheDocument()
    })

    // Click "ดูเนื้อหา"
    const viewButtons = screen.getAllByText('📄 ดูเนื้อหา')
    fireEvent.click(viewButtons[0])

    await waitFor(() => {
      expect(api.getEquityNoteContent).toHaveBeenCalledWith('30_Knowledge_Base/Stocks/AAPL/AAPL Deep Dive.md')
      expect(screen.getByText((content) => content.includes('AAPL Valuation Thesis'))).toBeInTheDocument()
    })


    // Click "ปิด" button to close modal
    const closeButton = screen.getByRole('button', { name: 'ปิด' })
    fireEvent.click(closeButton)

    await waitFor(() => {
      expect(screen.queryByText('# AAPL Valuation Thesis\nFull content of the note.')).not.toBeInTheDocument()
    })
  })
})

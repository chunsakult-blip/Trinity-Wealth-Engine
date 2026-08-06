import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { EquityNews } from './EquityNews'
import { api } from '../../api/client'

vi.mock('../../api/client', () => ({
  api: {
    getEquityNews: vi.fn(),
  },
}))

describe('EquityNews', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state initially', () => {
    vi.mocked(api.getEquityNews).mockImplementation(() => new Promise(() => {}))
    render(<EquityNews ticker="AAPL" />)
    expect(screen.getByText('กำลังโหลดข่าวสาร...')).toBeInTheDocument()
  })

  it('renders empty 404 state when no news found', async () => {
    vi.mocked(api.getEquityNews).mockRejectedValue({ status: 404, message: '404 Not Found' })
    render(<EquityNews ticker="AAPL" />)

    await waitFor(() => {
      expect(screen.getByText('ยังไม่มีข้อมูลข่าวสำหรับหุ้นตัวนี้ในระบบ')).toBeInTheDocument()
      expect(screen.getByText(/สั่งงานผ่านผู้จัดการ \(Manager Agent\)/)).toBeInTheDocument()
    })
  })

  it('renders error state on API failure', async () => {
    vi.mocked(api.getEquityNews).mockRejectedValue(new Error('Network error'))
    render(<EquityNews ticker="AAPL" />)

    await waitFor(() => {
      expect(screen.getByText('เกิดข้อผิดพลาด')).toBeInTheDocument()
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('renders news items successfully', async () => {
    vi.mocked(api.getEquityNews).mockResolvedValue({
      ticker: 'AAPL',
      market: 'US',
      last_updated: '2026-08-05 22:10:59',
      news_date: '2026-08-05',
      items: [
        {
          title: 'Apple Intelligence News',
          source: 'Reuters',
          link: 'https://example.com/news',
          published_at: '2026-08-05T20:00:00Z',
          age_hours: 2,
          freshness_reason: 'Fresh',
          is_stale: false,
          sources_count: 2,
        },
      ],
    })

    render(<EquityNews ticker="AAPL" />)

    await waitFor(() => {
      expect(screen.getByText('Apple Intelligence News')).toBeInTheDocument()
      expect(screen.getByText('ที่มา: Reuters')).toBeInTheDocument()
      expect(screen.getByText('2 sources')).toBeInTheDocument()
      expect(screen.getByText('อ่านต่อบน Reuters')).toBeInTheDocument()
    })
  })
})

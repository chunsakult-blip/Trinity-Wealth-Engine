import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { api } from '../api/client'
import { mockEquitySummary, mockEquityDetailAAPL } from '../mocks/equity'

vi.mock('../api/client', () => ({
  api: {
    getEquityLatest: vi.fn(),
    getEquityDetail: vi.fn(),
    createKanbanCard: vi.fn(),
    dispatchJob: vi.fn(),
    getActualPortfolioState: vi.fn(),
    getActualWatchlist: vi.fn(),
  },
}))

describe('Equity Page', () => {
  beforeEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.mocked(api.getActualPortfolioState).mockResolvedValue({
      last_updated: null,
      fx_rates: {},
      summary: { total_value_thb: 0, total_cost_basis_thb: 0, total_unrealized_profit: 0, passive_income_ytd: 0 },
      allocation_targets: [],
      holdings: [],
      price_refresh_info: null,
    })
    vi.mocked(api.getActualWatchlist).mockResolvedValue({
      last_updated: null,
      items: [],
    })
    vi.stubEnv('VITE_EQUITY_MOCK', 'false')
    vi.stubEnv('DEV', true as any)
    vi.resetModules()
  })

  const renderComponent = async (initialRoute = '/equity') => {
    // Dynamic import to ensure it reads the stubbed env vars
    const { default: Equity } = await import('./Equity')
    return render(
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/equity" element={<Equity />} />
          <Route path="/equity/:ticker" element={<Equity />} />
        </Routes>
      </MemoryRouter>
    )
  }

  it('renders list of equities from api', async () => {
    vi.mocked(api.getEquityLatest).mockResolvedValue(mockEquitySummary)

    await renderComponent()

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument()
      expect(screen.getByText('PTT')).toBeInTheDocument()
    })
  })

  it('filters list using search bar', async () => {
    vi.mocked(api.getEquityLatest).mockResolvedValue(mockEquitySummary)
    
    await renderComponent()
    
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument()
      expect(screen.getByText('PTT')).toBeInTheDocument()
    })
    
    const searchInput = screen.getAllByPlaceholderText('ค้นหาหุ้น (เช่น AAPL)...')[0]
    await userEvent.type(searchInput, 'pt')
    
    await waitFor(() => {
      expect(screen.queryByText('AAPL')).not.toBeInTheDocument()
      expect(screen.getByText('PTT')).toBeInTheDocument()
    })
  })

  it('renders not found state when api returns 404', async () => {
    vi.mocked(api.getEquityLatest).mockResolvedValue([])
    vi.mocked(api.getEquityDetail).mockRejectedValue({ status: 404, message: 'Not found' })

    await renderComponent('/equity/unknown')

    await waitFor(() => {
      expect(screen.getByText('ไม่พบข้อมูล')).toBeInTheDocument()
    })
  })

  it('renders detail view successfully', async () => {
    vi.mocked(api.getEquityLatest).mockResolvedValue(mockEquitySummary)
    vi.mocked(api.getEquityDetail).mockResolvedValue(mockEquityDetailAAPL)

    await renderComponent('/equity/aapl')

    await waitFor(() => {
      // The Base Case Summary should appear
      expect(screen.getByText('Base Case Summary')).toBeInTheDocument()
      expect(screen.getByText('Apple Inc.')).toBeInTheDocument()
    })
  })

  it('เปิด Modal พร้อม ticker เดิมเมื่อกดปุ่ม 🔄 ในหน้า Detail', async () => {
    vi.mocked(api.getEquityLatest).mockResolvedValue(mockEquitySummary)
    vi.mocked(api.getEquityDetail).mockResolvedValue(mockEquityDetailAAPL)

    await renderComponent('/equity/aapl')
    await waitFor(() => expect(screen.getByText('Apple Inc.')).toBeInTheDocument())

    await userEvent.click(screen.getByTitle('วิเคราะห์ใหม่และดึงข่าวล่าสุด'))

    expect(screen.getByPlaceholderText('เช่น AAPL, NVDA, PTT.BK')).toHaveValue('AAPL')
  })

  it('สร้างการ์ดและ dispatch งานสำเร็จแล้วแสดง Toast พร้อมปุ่มไปดู Kanban', async () => {
    vi.mocked(api.getEquityLatest).mockResolvedValue(mockEquitySummary)
    vi.mocked(api.getEquityDetail).mockResolvedValue(mockEquityDetailAAPL)
    vi.mocked(api.createKanbanCard).mockResolvedValue({
      created: true,
      card: {
        card_id: 'card-1', title: 'วิเคราะห์หุ้น NVDA (US)', prompt: 'p', column_name: 'backlog',
        job_id: null, flow: 'manager', scope: 'both', display_seq: 1, discord_notify: true,
        is_verified: true, created_at: 1, updated_at: 1,
      },
    })
    vi.mocked(api.dispatchJob).mockResolvedValue({
      job_id: 'job-1', status: 'running', card_id: 'card-1', error_message: null,
      current_node: null, interrupt_payload: null, log_count: 0, created_at: 1, updated_at: 1,
    })

    await renderComponent('/equity/aapl')
    await waitFor(() => expect(screen.getByText('Apple Inc.')).toBeInTheDocument())

    await userEvent.click(screen.getByTitle('วิเคราะห์ใหม่และดึงข่าวล่าสุด'))
    const tickerInput = screen.getByPlaceholderText('เช่น AAPL, NVDA, PTT.BK')
    await userEvent.clear(tickerInput)
    await userEvent.type(tickerInput, 'nvda')
    await userEvent.click(screen.getByRole('button', { name: '🚀 สร้างการ์ดและเริ่มวิเคราะห์' }))

    await waitFor(() => {
      expect(screen.getByText('สั่งงานวิเคราะห์หุ้น NVDA และดึงข่าวเรียบร้อย')).toBeInTheDocument()
      expect(screen.getByText('ดูสถานะใน Kanban')).toBeInTheDocument()
    })
    // Modal ต้องปิดหลัง dispatch สำเร็จ
    expect(screen.queryByText('📊 วิเคราะห์หุ้นและดึงข่าวล่าสุด')).not.toBeInTheDocument()
  })
})

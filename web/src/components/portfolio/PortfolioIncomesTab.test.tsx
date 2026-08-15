import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import PortfolioIncomesTab from './PortfolioIncomesTab'
import { api } from '../../api/client'
import type { ActualPortfolioStateDTO } from '../../api/types'

vi.mock('../../api/client', () => ({
  api: {
    syncDividends: vi.fn(),
    getActualPortfolioState: vi.fn(),
  },
}))

describe('PortfolioIncomesTab', () => {
  const mockState: ActualPortfolioStateDTO = {
    last_updated: '2026-08-15T10:00:00',
    fx_rates: { USDTHB: 36.5 },
    summary: {
      total_value_thb: 250000.0,
      total_cost_basis_thb: 200000.0,
      total_unrealized_profit: 50000.0,
      passive_income_ytd: 12000.0,
      total_accumulated_dividend: 15450.0,
    },
    allocation_targets: [],
    holdings: [
      {
        symbol: 'AAPL',
        asset_type: 'Stock',
        units: 10.0,
        bucket_id: null,
        avg_cost_usd: 150.0,
        avg_cost_thb: 5475.0,
        current_price_usd: 180.0,
        current_price_thb: 6570.0,
        market_value_thb: 65700.0,
        unrealized_pnl_percent: 20.0,
        unrealized_pnl_value: 10950.0,
        market_cap_tier: 'Mega',
        yield_on_cost: null,
        company_name: 'Apple Inc.',
        pe_ratio: 28.5,
        eps: 6.3,
        payout_ratio: 0.15,
        market_cap_value: null,
        dividend_per_share: 0.96,
        dividend_yield: 0.0053,
        accumulated_dividend_thb: 3450.0,
        accumulated_dividend_native: 94.52,
        upcoming_dividend_thb: 87.6,
        upcoming_dividend_native: 2.4,
        dividend_rounds: [
          {
            symbol: 'AAPL',
            ex_date: '2026-08-01',
            pay_date: '2026-08-20',
            dps: 0.24,
            currency: 'USD',
            units_held: 10.0,
            status: 'upcoming',
            gross_native: 2.4,
            net_native: 2.04,
            gross_thb: 87.6,
            tax_rate: 0.15,
            net_thb: 74.46,
            fx_rate: 36.5,
          },
          {
            symbol: 'AAPL',
            ex_date: '2026-05-10',
            pay_date: '2026-05-25',
            dps: 0.24,
            currency: 'USD',
            units_held: 10.0,
            status: 'received',
            gross_native: 2.4,
            net_native: 2.04,
            gross_thb: 87.6,
            tax_rate: 0.15,
            net_thb: 74.46,
            fx_rate: 36.5,
          },
        ],
        dividend_source: 'synced',
        fundamentals_updated_at: null,
      },
      {
        symbol: 'PTT',
        asset_type: 'Stock',
        units: 1000.0,
        bucket_id: null,
        avg_cost_usd: null,
        avg_cost_thb: 35.0,
        current_price_usd: null,
        current_price_thb: 36.0,
        market_value_thb: 36000.0,
        unrealized_pnl_percent: 2.85,
        unrealized_pnl_value: 1000.0,
        market_cap_tier: 'Large',
        yield_on_cost: null,
        company_name: 'PTT Public Company',
        pe_ratio: 10.2,
        eps: 3.5,
        payout_ratio: 0.55,
        market_cap_value: null,
        dividend_per_share: 2.0,
        dividend_yield: 0.055,
        accumulated_dividend_thb: 8500.0,
        accumulated_dividend_native: 8500.0,
        dividend_rounds: [
          {
            symbol: 'PTT',
            ex_date: '2026-03-01',
            pay_date: '2026-03-20',
            dps: 2.0,
            currency: 'THB',
            units_held: 1000.0,
            status: 'received',
            gross_native: 2000.0,
            net_native: 1800.0,
            gross_thb: 2000.0,
            tax_rate: 0.1,
            net_thb: 1800.0,
            fx_rate: 1.0,
          },
        ],
        dividend_source: 'manual',
        fundamentals_updated_at: null,
      },
      {
        symbol: 'CASH_THB',
        asset_type: 'Cash',
        units: 50000.0,
        bucket_id: null,
        avg_cost_usd: null,
        avg_cost_thb: 1.0,
        current_price_usd: null,
        current_price_thb: 1.0,
        market_value_thb: 50000.0,
        unrealized_pnl_percent: null,
        unrealized_pnl_value: null,
        market_cap_tier: null,
        yield_on_cost: null,
        company_name: null,
        pe_ratio: null,
        eps: null,
        payout_ratio: null,
        market_cap_value: null,
        dividend_per_share: null,
        dividend_yield: null,
        accumulated_dividend_thb: null,
        dividend_source: null,
        fundamentals_updated_at: null,
      },
    ],
    price_refresh_info: null,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders KPI summary cards and holdings table correctly with native USD', () => {
    render(
      <PortfolioIncomesTab
        state={mockState}
        selectedPortfolioId="default"
        onSuccess={vi.fn()}
      />
    )

    // Check KPIs
    expect(screen.getByText('เงินปันผลสะสมทั้งหมด (Total Accumulated)')).toBeInTheDocument()
    expect(screen.getAllByText('฿15,450.00').length).toBeGreaterThan(0)
    expect(screen.getByText('฿12,000.00')).toBeInTheDocument()

    // Check Holdings (Cash excluded from table)
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('PTT')).toBeInTheDocument()
    expect(screen.queryByText('CASH_THB')).not.toBeInTheDocument()

    // Check USD native rendering ($94.52 with (฿3,450.00))
    expect(screen.getByText('$94.52')).toBeInTheDocument()
    expect(screen.getByText('(฿3,450.00)')).toBeInTheDocument()

    // Check badges
    expect(screen.getByText('Synced')).toBeInTheDocument()
    expect(screen.getByText('Manual')).toBeInTheDocument()
  })

  it('switches between Received and Upcoming sub-tabs', () => {
    render(
      <PortfolioIncomesTab
        state={mockState}
        selectedPortfolioId="default"
        onSuccess={vi.fn()}
      />
    )

    // Initially in Received tab
    expect(screen.getByText('เงินปันผลที่ได้รับ (Net Received)')).toBeInTheDocument()

    // Switch to Upcoming tab
    const upcomingTabBtn = screen.getByRole('button', { name: /รอรับเงิน \(Upcoming\)/ })
    fireEvent.click(upcomingTabBtn)

    // Check Upcoming UI elements
    expect(screen.getByText('เงินปันผลที่รอรับทั้งหมด (Total Upcoming)')).toBeInTheDocument()
    expect(screen.getByText('วันจ่ายเงินจริง (Pay Date)')).toBeInTheDocument()
    expect(screen.getByText('2026-08-20')).toBeInTheDocument()
  })

  it('handles dividend sync click and updates state', async () => {
    const mockOnSuccess = vi.fn()
    const syncResponse = {
      synced_symbols: 1,
      total_rounds: 2,
      total_received_rounds: 1,
      total_upcoming_rounds: 1,
      total_dividend_thb: 3450.0,
      total_upcoming_thb: 74.46,
      skipped_manual: ['PTT'],
      details: {
        AAPL: [
          {
            symbol: 'AAPL',
            ex_date: '2026-08-01',
            pay_date: '2026-08-20',
            dps: 0.24,
            currency: 'USD',
            units_held: 10.0,
            status: 'upcoming' as const,
            gross_native: 2.4,
            net_native: 2.04,
            gross_thb: 87.6,
            tax_rate: 0.15,
            net_thb: 74.46,
            fx_rate: 36.5,
          },
        ],
      },
    }

    vi.mocked(api.syncDividends).mockResolvedValue(syncResponse)
    vi.mocked(api.getActualPortfolioState).mockResolvedValue(mockState)

    render(
      <PortfolioIncomesTab
        state={mockState}
        selectedPortfolioId="default"
        onSuccess={mockOnSuccess}
      />
    )

    const syncBtn = screen.getByText('ซิงค์เงินปันผลอัตโนมัติ')
    fireEvent.click(syncBtn)

    await waitFor(() => {
      expect(api.syncDividends).toHaveBeenCalledWith('default')
      expect(api.getActualPortfolioState).toHaveBeenCalledWith(false, false, 'default')
      expect(mockOnSuccess).toHaveBeenCalledWith(mockState)
    })

    // Check banner details
    expect(screen.getByText(/ซิงค์สำเร็จ 1 สินทรัพย์ รวม 2 รอบการจ่าย/)).toBeInTheDocument()
    expect(screen.getByText(/ข้าม PTT เนื่องจากเคยถูกแก้ไขแบบกำหนดเอง/)).toBeInTheDocument()
  })

  it('filters holdings list via search input and source buttons', () => {
    render(
      <PortfolioIncomesTab
        state={mockState}
        selectedPortfolioId="default"
        onSuccess={vi.fn()}
      />
    )

    // Search for AAPL
    const searchInput = screen.getByPlaceholderText('🔍 ค้นหาสัญลักษณ์หุ้น...')
    fireEvent.change(searchInput, { target: { value: 'AAPL' } })

    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.queryByText('PTT')).not.toBeInTheDocument()

    // Filter by Manual
    fireEvent.change(searchInput, { target: { value: '' } })
    const manualFilterBtn = screen.getByText('✏️ Manual')
    fireEvent.click(manualFilterBtn)

    expect(screen.queryByText('AAPL')).not.toBeInTheDocument()
    expect(screen.getByText('PTT')).toBeInTheDocument()
  })

  it('opens and closes detailed dividend rounds modal with status badges and native metrics', async () => {
    render(
      <PortfolioIncomesTab
        state={mockState}
        selectedPortfolioId="default"
        onSuccess={vi.fn()}
      />
    )

    // Click "🔍 ดู 2 รอบ" on AAPL
    const viewBtn = screen.getByText('🔍 ดู 2 รอบ')
    fireEvent.click(viewBtn)

    // Check modal open
    expect(screen.getByText('รายละเอียดรอบเงินปันผล: AAPL')).toBeInTheDocument()
    expect(screen.getByText('2026-08-01')).toBeInTheDocument()
    expect(screen.getByText('2026-05-10')).toBeInTheDocument()
    expect(screen.getByText('⏳ รอจ่าย')).toBeInTheDocument()
    expect(screen.getByText('✅ ได้รับแล้ว')).toBeInTheDocument()

    // Close modal
    fireEvent.click(screen.getByText('ปิด'))
    expect(screen.queryByText('รายละเอียดรอบเงินปันผล: AAPL')).not.toBeInTheDocument()
  })
})

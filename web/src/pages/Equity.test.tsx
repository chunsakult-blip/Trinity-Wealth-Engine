import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { api } from '../api/client'
import { mockEquitySummary, mockEquityDetailAAPL } from '../mocks/equity'

vi.mock('../api/client', () => ({
  api: {
    getEquityLatest: vi.fn(),
    getEquityDetail: vi.fn(),
  },
}))

describe('Equity Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
    
    const searchInput = screen.getByPlaceholderText('ค้นหาหุ้น (เช่น AAPL)...')
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
})

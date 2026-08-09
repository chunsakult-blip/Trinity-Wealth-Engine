import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Macro from './Macro'
import { api } from '../api/client'

vi.mock('../api/client', () => ({
  api: {
    getMacroDashboard: vi.fn(),
    createKanbanCard: vi.fn(),
    dispatchJob: vi.fn(),
  },
}))

const mockMacroDashboard = {
  overall_regime: 'Goldilocks',
  time_horizon: '12m',
  conviction_level: 'High',
  conviction_rationale: 'Growth is robust while inflation continues to moderate.',
  quant_narrative_alignment: 'Aligned',
  key_assumptions: ['Fed rate cuts expected'],
  regime_probabilities: { Goldilocks: 0.6, Reflation: 0.2, Stagflation: 0.1, Recession: 0.1 },
  warnings: [],
  asset_allocation: [],
  pair_trades: [],
  risk_scenarios: [],
  evaluated_at: '2026-08-08',
}

describe('Macro Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders macro dashboard and triggers analysis update via button', async () => {
    vi.mocked(api.getMacroDashboard).mockResolvedValue(mockMacroDashboard as any)
    vi.mocked(api.createKanbanCard).mockResolvedValue({
      created: true,
      card: {
        card_id: 'macro-card-1', title: 'วิเคราะห์ภาวะเศรษฐกิจมหภาค (Macro Analysis)', prompt: 'p', column_name: 'backlog',
        job_id: null, flow: 'manager', scope: 'both', display_seq: 1, discord_notify: true,
        is_verified: true, created_at: 1, updated_at: 1,
      },
    })
    vi.mocked(api.dispatchJob).mockResolvedValue({
      job_id: 'job-macro-1', status: 'running', card_id: 'macro-card-1', error_message: null,
      current_node: null, interrupt_payload: null, log_count: 0, created_at: 1, updated_at: 1,
    })

    render(
      <MemoryRouter>
        <Macro />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getAllByText('Goldilocks')[0]).toBeInTheDocument()
    })

    const updateBtn = screen.getByRole('button', { name: /อัปเดตบทวิเคราะห์/ })
    expect(updateBtn).toBeInTheDocument()

    await userEvent.click(updateBtn)

    await waitFor(() => {
      expect(api.createKanbanCard).toHaveBeenCalledWith(
        'วิเคราะห์ภาวะเศรษฐกิจมหภาค (Macro Analysis)',
        'manager',
        'วิเคราะห์ภาวะเศรษฐกิจมหภาค (Macro Intelligence & Regime Analysis) ล่าสุดพร้อมประเมิน Asset Allocation',
        'both'
      )
      expect(api.dispatchJob).toHaveBeenCalledWith(
        'วิเคราะห์ภาวะเศรษฐกิจมหภาค (Macro Intelligence & Regime Analysis) ล่าสุดพร้อมประเมิน Asset Allocation',
        'macro-card-1',
        'manager',
        'both'
      )
      expect(screen.getByText('สั่งงานวิเคราะห์ภาวะเศรษฐกิจมหภาคเรียบร้อย')).toBeInTheDocument()
      expect(screen.getByText('ดูสถานะใน Kanban')).toBeInTheDocument()
    })
  })
})

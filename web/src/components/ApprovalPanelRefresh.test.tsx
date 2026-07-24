import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import ApprovalPanel from './ApprovalPanel'
import type { YoutubePitchApprovalPayload } from '../api/types'

it('offers a source refresh action when every YouTube pitch is unselectable', async () => {
  const payload: YoutubePitchApprovalPayload = {
    type: 'youtube_pitch_approval',
    pitches: [{
      pitch_id: 'blocked-1', working_titles: ['One', 'Two', 'Three'], target_audience: 'Investor',
      core_hook: 'Hook', key_questions_to_answer: ['Q1'], research_hypotheses: [],
      source_event_ids: ['ev-1'], source_links: ['https://example.test'], source_titles: ['Source'],
      recommended_format: '15m', estimated_impact: 'High', source_readiness: 'needs_refresh',
    }],
  }
  const onApprove = vi.fn()
  render(<ApprovalPanel payload={payload} onApprove={onApprove} />)

  expect(screen.getByRole('alert')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'ค้นหาแหล่งข่าวใหม่' }))
  expect(onApprove).toHaveBeenCalledWith([], [], [], [], 'refresh_sources')
})

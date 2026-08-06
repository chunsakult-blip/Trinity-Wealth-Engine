import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ScoreRing from './ScoreRing'

describe('ScoreRing', () => {
  it('renders rounded score value', () => {
    render(<ScoreRing score={82.5} />)
    expect(screen.getByText('83')).toBeInTheDocument()
  })

  it('displays N/A for null score', () => {
    render(<ScoreRing score={null} />)
    expect(screen.getByText('N/A')).toBeInTheDocument()
  })

  it('applies emerald color for score >= 70', () => {
    render(<ScoreRing score={82.5} />)
    expect(screen.getByText('83')).toHaveClass('text-emerald-600')
  })

  it('applies amber color for score 40-69', () => {
    render(<ScoreRing score={55} />)
    expect(screen.getByText('55')).toHaveClass('text-amber-600')
  })

  it('applies red color for score < 40', () => {
    render(<ScoreRing score={20} />)
    expect(screen.getByText('20')).toHaveClass('text-red-600')
  })
})

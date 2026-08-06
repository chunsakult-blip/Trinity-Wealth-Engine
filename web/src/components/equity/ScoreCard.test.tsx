import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ScoreCard } from './ScoreCard'
describe('ScoreCard', () => {
  it('renders title and score', () => {
    render(<ScoreCard title="Composite" score={85} />)
    expect(screen.getByText('Composite')).toBeInTheDocument()
    expect(screen.getByText('85')).toBeInTheDocument()
  })

  it('renders subtitle if provided', () => {
    render(<ScoreCard title="Test" score={50} subtitle="Test subtitle" />)
    expect(screen.getByText('Test subtitle')).toBeInTheDocument()
  })

  it('displays N/A for null score', () => {
    render(<ScoreCard title="Test" score={null} />)
    expect(screen.getByText('N/A')).toBeInTheDocument()
  })

  it('applies red color for score < 40', () => {
    const { container } = render(<ScoreCard title="Test" score={39} />)
    expect(container.firstChild).toHaveClass('bg-red-50')
    expect(screen.getByText('39')).toHaveClass('text-red-600')
  })

  it('applies amber color for score 40-69', () => {
    const { container } = render(<ScoreCard title="Test" score={69} />)
    expect(container.firstChild).toHaveClass('bg-amber-50')
    expect(screen.getByText('69')).toHaveClass('text-amber-600')
  })

  it('applies emerald color for score >= 70', () => {
    const { container } = render(<ScoreCard title="Test" score={70} />)
    expect(container.firstChild).toHaveClass('bg-emerald-50')
    expect(screen.getByText('70')).toHaveClass('text-emerald-600')
  })

  it('renders icon when provided', () => {
    render(<ScoreCard title="Value" score={65} icon="💰" />)
    expect(screen.getByText('💰')).toBeInTheDocument()
  })

  it('renders no icon when not provided', () => {
    render(<ScoreCard title="Value" score={65} />)
    expect(screen.queryByText('💰')).not.toBeInTheDocument()
  })
})

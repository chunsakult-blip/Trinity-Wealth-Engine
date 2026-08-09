import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import RegimeProbabilityChart from './RegimeProbabilityChart'

describe('RegimeProbabilityChart', () => {
  it('เรียง regime ตามลำดับมาตรฐานก่อน แล้วต่อด้วยชื่อที่ไม่รู้จัก', () => {
    render(
      <RegimeProbabilityChart
        probabilities={{ Recession: 0.1, Goldilocks: 0.4, CustomRegime: 0.5 }}
      />
    )
    const labels = screen.getAllByText(/Goldilocks|Recession|CustomRegime/).map((el) => el.textContent)
    expect(labels).toEqual(['Goldilocks', 'Recession', 'CustomRegime'])
  })

  it('แปลงความน่าจะเป็นเป็นเปอร์เซ็นต์ปัดเศษ', () => {
    render(<RegimeProbabilityChart probabilities={{ Goldilocks: 0.456 }} />)
    expect(screen.getByText('46%')).toBeInTheDocument()
  })

  it('รองรับค่าความน่าจะเป็นที่เป็นเปอร์เซ็นต์ > 1 (เช่น 15, 47.5) และข้อความ %', () => {
    render(
      <RegimeProbabilityChart
        probabilities={{
          Goldilocks: 15,
          Reflation: 12.5,
          Stagflation: '25%',
          Recession: 47.5,
        }}
      />
    )
    expect(screen.getByText('15%')).toBeInTheDocument()
    expect(screen.getByText('13%')).toBeInTheDocument()
    expect(screen.getByText('25%')).toBeInTheDocument()
    expect(screen.getByText('48%')).toBeInTheDocument()
  })

  it('probabilities ว่าง → ไม่ crash', () => {
    const { container } = render(<RegimeProbabilityChart probabilities={{}} />)
    expect(container.firstChild).not.toBeNull()
  })
})

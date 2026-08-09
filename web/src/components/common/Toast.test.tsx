import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import Toast from './Toast'

describe('Toast Component', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders message correctly', () => {
    render(<Toast message="สร้างการ์ดสำเร็จ" />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('สร้างการ์ดสำเร็จ')).toBeInTheDocument()
  })

  it('calls onAction when action button is clicked', () => {
    const handleAction = vi.fn()
    render(<Toast message="งานกำลังรัน" actionLabel="ดูสถานะ" onAction={handleAction} />)

    const actionButton = screen.getByText('ดูสถานะ')
    expect(actionButton).toBeInTheDocument()

    fireEvent.click(actionButton)
    expect(handleAction).toHaveBeenCalledTimes(1)
  })

  it('closes automatically after durationMs', () => {
    const handleClose = vi.fn()
    render(<Toast message="จะปิดอัตโนมัติ" durationMs={3000} onClose={handleClose} />)

    act(() => {
      vi.advanceTimersByTime(3000)
    })
    act(() => {
      vi.advanceTimersByTime(200)
    })

    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when close icon is clicked', () => {
    const handleClose = vi.fn()
    render(<Toast message="ข้อความทดสอบ" onClose={handleClose} />)

    const closeButton = screen.getByRole('button', { name: 'Close Toast' })
    fireEvent.click(closeButton)

    act(() => {
      vi.advanceTimersByTime(200)
    })

    expect(handleClose).toHaveBeenCalledTimes(1)
  })
})

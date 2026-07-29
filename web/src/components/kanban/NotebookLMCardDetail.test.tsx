import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import NotebookLMCardDetail from './NotebookLMCardDetail'
import { api } from '../../api/client'
import type { KanbanCardDTO } from '../../api/types'

vi.mock('../../api/client', () => ({
  api: {
    generateNotebookLMAudio: vi.fn(),
    getNotebookLMStatus: vi.fn(),
    getNotebookLMAvailableSources: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

function makeCard(overrides: Partial<KanbanCardDTO> = {}): KanbanCardDTO {
  return {
    card_id: 'card-1',
    title: 'NotebookLM Audio ของฉัน',
    prompt: null,
    column_name: 'backlog',
    job_id: null,
    flow: 'notebooklm',
    scope: 'both',
    display_seq: null,
    discord_notify: true,
    is_verified: true,
    created_at: 1_700_000_000,
    updated_at: 1_700_000_000,
    ...overrides,
  }
}

describe('NotebookLMCardDetail — ยังไม่เลือกไฟล์ (card.prompt ว่าง)', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('โหลดรายชื่อ Briefing Book มาให้เลือก และปุ่มยืนยันถูก disable จนกว่าจะเลือก', async () => {
    vi.mocked(api.getNotebookLMAvailableSources).mockResolvedValue([
      { file_path: '/vault/a.md', title: 'หัวข้อ A', is_verified: true },
      { file_path: '/vault/b.md', title: 'หัวข้อ B', is_verified: false },
    ])

    render(<NotebookLMCardDetail card={makeCard()} onCardTransition={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('🟢 หัวข้อ A')).toBeInTheDocument()
    })
    expect(screen.getByText('🟡 หัวข้อ B')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ยืนยันและสร้าง Audio' })).toBeDisabled()
  })

  it('แสดงข้อความเมื่อไม่มีไฟล์ให้เลือกเลย', async () => {
    vi.mocked(api.getNotebookLMAvailableSources).mockResolvedValue([])

    render(<NotebookLMCardDetail card={makeCard()} onCardTransition={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText(/ไม่พบไฟล์ใน NotebookLM_Sources/)).toBeInTheDocument()
    })
  })

  it('เลือกไฟล์แล้วกดยืนยัน เรียก generate พร้อม card_id และ path ที่เลือก', async () => {
    vi.mocked(api.getNotebookLMAvailableSources).mockResolvedValue([
      { file_path: '/vault/a.md', title: 'หัวข้อ A', is_verified: true },
    ])
    vi.mocked(api.generateNotebookLMAudio).mockResolvedValue({ job_id: 'job-1', status: 'queued' })
    const onCardTransition = vi.fn()

    render(<NotebookLMCardDetail card={makeCard()} onCardTransition={onCardTransition} />)

    await waitFor(() => screen.getByRole('combobox'))
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '/vault/a.md' } })
    fireEvent.click(screen.getByRole('button', { name: 'ยืนยันและสร้าง Audio' }))

    await waitFor(() => {
      expect(api.generateNotebookLMAudio).toHaveBeenCalledWith('card-1', '/vault/a.md')
    })
    expect(onCardTransition).toHaveBeenCalled()
  })
})

describe('NotebookLMCardDetail — เลือกไฟล์แล้ว (card.prompt มีค่า)', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('แสดง badge verified/unverified ของการ์ด', async () => {
    vi.mocked(api.getNotebookLMStatus).mockResolvedValue({
      job_id: 'job-2', status: 'running', audio_path: null, notebook_id: 'nb-1', error: null,
    })
    render(
      <NotebookLMCardDetail
        card={makeCard({ prompt: '/vault/a.md', job_id: 'job-2', column_name: 'executing', is_verified: false })}
        onCardTransition={vi.fn()}
      />
    )
    await waitFor(() => {
      expect(screen.getByText('🟡 unverified draft')).toBeInTheDocument()
    })
  })

  it('แสดงชื่อไฟล์ที่เลือกไว้ (ตัด path ออก เหลือแค่ชื่อไฟล์)', async () => {
    vi.mocked(api.getNotebookLMStatus).mockResolvedValue({
      job_id: 'job-2', status: 'running', audio_path: null, notebook_id: 'nb-1', error: null,
    })
    render(
      <NotebookLMCardDetail
        card={makeCard({
          prompt: 'C:\\vault\\NotebookLM_Sources\\2026-07-19_ทดสอบ.md',
          job_id: 'job-2', column_name: 'executing',
        })}
        onCardTransition={vi.fn()}
      />
    )
    await waitFor(() => {
      expect(screen.getByText(/2026-07-19_ทดสอบ\.md/)).toBeInTheDocument()
    })
    expect(screen.queryByText(/C:\\vault/)).not.toBeInTheDocument()
  })

  it('poll สถานะและโชว์ label ระหว่างทำงาน ไม่มีปุ่มลองใหม่ระหว่างนี้', async () => {
    vi.mocked(api.getNotebookLMStatus).mockResolvedValue({
      job_id: 'job-2', status: 'running', audio_path: null, notebook_id: 'nb-1', error: null,
    })

    render(
      <NotebookLMCardDetail
        card={makeCard({ prompt: '/vault/a.md', job_id: 'job-2', column_name: 'executing' })}
        onCardTransition={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(api.getNotebookLMStatus).toHaveBeenCalledWith('job-2')
    })
    expect(screen.queryByRole('button', { name: 'ลองใหม่' })).not.toBeInTheDocument()
  })

  it('แสดงสถานะเสร็จสมบูรณ์และ audio path เมื่อ column เป็น done', async () => {
    vi.mocked(api.getNotebookLMStatus).mockResolvedValue({
      job_id: 'job-3', status: 'done', audio_path: '/vault/NotebookLM_Audio/test_a1b2c3d4.mp3', notebook_id: 'nb-1', error: null,
    })

    render(
      <NotebookLMCardDetail
        card={makeCard({ prompt: '/vault/a.md', job_id: 'job-3', column_name: 'done' })}
        onCardTransition={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Audio พร้อมแล้ว')).toBeInTheDocument()
    })
    expect(screen.getByText(/test_a1b2c3d4\.mp3/)).toBeInTheDocument()
  })

  it('แสดง error message และปุ่มลองใหม่เมื่องานล้มเหลว', async () => {
    vi.mocked(api.getNotebookLMStatus).mockResolvedValue({
      job_id: 'job-4', status: 'error', audio_path: null, notebook_id: null,
      error: "NotebookLM auth ยังไม่พร้อม — รัน `nlm login` ก่อน",
    })

    render(
      <NotebookLMCardDetail
        card={makeCard({ prompt: '/vault/a.md', job_id: 'job-4', column_name: 'backlog' })}
        onCardTransition={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/nlm login/)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'ลองใหม่' })).toBeInTheDocument()
  })

  it('กดลองใหม่เรียก generate โดยไม่ส่ง briefing_file_path (ใช้ card.prompt เดิม)', async () => {
    vi.mocked(api.getNotebookLMStatus).mockResolvedValue({
      job_id: 'job-5', status: 'error', audio_path: null, notebook_id: null, error: 'ล้มเหลว',
    })
    vi.mocked(api.generateNotebookLMAudio).mockResolvedValue({ job_id: 'job-5', status: 'queued' })

    render(
      <NotebookLMCardDetail
        card={makeCard({ prompt: '/vault/a.md', job_id: 'job-5', column_name: 'backlog' })}
        onCardTransition={vi.fn()}
      />
    )

    await waitFor(() => screen.getByRole('button', { name: 'ลองใหม่' }))
    fireEvent.click(screen.getByRole('button', { name: 'ลองใหม่' }))

    await waitFor(() => {
      expect(api.generateNotebookLMAudio).toHaveBeenCalledWith('card-1', undefined)
    })
  })
})

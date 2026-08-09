import { beforeEach, describe, expect, it } from 'vitest'
import { loadQuickTemplates, saveQuickTemplates, type QuickTemplate } from './quickTemplateStorage'

const STORAGE_KEY = 'kanban-quick-templates'

describe('quickTemplateStorage', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('ไม่มีข้อมูลใน storage → คืน default templates', () => {
    const templates = loadQuickTemplates()
    expect(templates.length).toBeGreaterThan(0)
    expect(templates[0]?.flow).toBe('manager')
  })

  it('JSON เสีย → คืน default ไม่ throw', () => {
    window.localStorage.setItem(STORAGE_KEY, '{not-json')
    expect(() => loadQuickTemplates()).not.toThrow()
    expect(loadQuickTemplates().length).toBeGreaterThan(0)
  })

  it('ข้อมูลไม่ใช่ array (โดนเขียนทับผิดรูป) → คืน default', () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ hacked: true }))
    const templates = loadQuickTemplates()
    expect(Array.isArray(templates)).toBe(true)
    expect(templates[0]?.label).toBeTruthy()
  })

  it('save แล้ว load กลับมาได้ค่าเดิม (roundtrip) — ถ้ามี templates ครบอยู่แล้วไม่ migrate ซ้ำ', () => {
    const custom: QuickTemplate[] = [
      { label: 'ทดสอบ', instruction: 'คำสั่งทดสอบ', flow: 'manager', scope: 'both' },
      { label: 'วิเคราะห์หุ้นและดึงข่าว (Equity & News)', instruction: 'วิเคราะห์หุ้น', flow: 'manager', scope: 'both' },
      { label: 'NotebookLM ของฉันเอง', instruction: '', flow: 'notebooklm', scope: 'both' },
    ]
    saveQuickTemplates(custom)
    expect(loadQuickTemplates()).toEqual(custom)
  })

  it('default templates มีปุ่มลัด NotebookLM Audio และ Equity & News', () => {
    const templates = loadQuickTemplates()
    const notebooklm = templates.find((t) => t.flow === 'notebooklm')
    expect(notebooklm).toBeTruthy()
    expect(notebooklm?.instruction).toBe('') // ต้องว่าง ไม่งั้น Drawer จะข้ามหน้าเลือกไฟล์ไปผิดๆ

    const equityNews = templates.find((t) => t.label.includes('วิเคราะห์หุ้นและดึงข่าว'))
    expect(equityNews).toBeTruthy()
  })

  it('ผู้ใช้เดิมที่ save templates ไว้ก่อนมี flow นี้ → เติมให้อัตโนมัติครั้งเดียว', () => {
    const legacy: QuickTemplate[] = [
      { label: 'ของเดิมที่ผู้ใช้ปรับแต่งเอง', instruction: 'คำสั่งเดิม', flow: 'manager', scope: 'both' },
    ]
    saveQuickTemplates(legacy)

    const migrated = loadQuickTemplates()
    expect(migrated).toEqual([
      legacy[0],
      { label: 'วิเคราะห์หุ้นและดึงข่าว (Equity & News)', instruction: 'วิเคราะห์หุ้น AAPL และดึงข่าวล่าสุดพร้อมประเมิน Valuation', flow: 'manager', scope: 'both' },
      { label: 'สร้าง Audio Overview (NotebookLM)', instruction: '', flow: 'notebooklm', scope: 'both' },
    ])

    // ต้อง persist กลับลง localStorage ด้วย ไม่ใช่แค่คืนค่าตอน runtime เฉยๆ — โหลดซ้ำต้องไม่เพิ่มซ้ำอีก
    const raw = window.localStorage.getItem(STORAGE_KEY)
    expect(JSON.parse(raw!)).toEqual(migrated)
    expect(loadQuickTemplates()).toEqual(migrated)
  })
})

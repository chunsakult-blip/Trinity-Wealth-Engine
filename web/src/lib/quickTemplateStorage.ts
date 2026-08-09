export interface QuickTemplate {
  label: string
  instruction: string
  flow: string
  scope: string
}

const STORAGE_KEY = 'kanban-quick-templates'

// instruction ว่างโดยตั้งใจ — flow นี้ไม่ได้ใช้ prompt เป็นคำสั่งแชท (ผู้ใช้เลือกไฟล์ Briefing Book
// ทีหลังใน Drawer) ถ้าใส่ข้อความจะถูกเก็บเป็น card.prompt แล้วทำให้ Drawer คิดว่าเลือกไฟล์ไปแล้ว
// ข้ามหน้าเลือกไฟล์ไปเลยผิดๆ (ดู NotebookLMCardDetail.tsx: !card.prompt เป็นตัวตัดสินว่าจะโชว์ picker)
const NOTEBOOKLM_QUICK_TEMPLATE: QuickTemplate = {
  label: 'สร้าง Audio Overview (NotebookLM)', instruction: '', flow: 'notebooklm', scope: 'both',
}

const EQUITY_NEWS_QUICK_TEMPLATE: QuickTemplate = {
  label: 'วิเคราะห์หุ้นและดึงข่าว (Equity & News)',
  instruction: 'วิเคราะห์หุ้น AAPL และดึงข่าวล่าสุดพร้อมประเมิน Valuation',
  flow: 'manager',
  scope: 'both',
}

const DEFAULT_TEMPLATES: QuickTemplate[] = [
  { label: 'วิเคราะห์เศรษฐกิจมหภาค', instruction: 'วิเคราะห์เศรษฐกิจมหภาคและจัดสรรพอร์ตประจำวัน', flow: 'manager', scope: 'both' },
  EQUITY_NEWS_QUICK_TEMPLATE,
  { label: 'ดึงข่าวล่าสุด', instruction: 'ดึงข่าวเศรษฐกิจและการลงทุนล่าสุด สรุปประเด็นสำคัญ', flow: 'news_youtube', scope: 'news' },
  { label: 'ดึงสรุปคลิป YouTube', instruction: 'ดึงสรุปคลิป YouTube ช่องการลงทุนที่ติดตามไว้ล่าสุด', flow: 'news_youtube', scope: 'youtube' },
  { label: 'หาไอเดียทำคลิป (ย้อนหลัง 3 วัน)', instruction: 'หาไอเดียทำคลิป YouTube เชิงลึก [lookback_days=3]', flow: 'youtube_pitch', scope: 'both' },
  { label: 'หาไอเดียทำคลิป (กำหนดช่วงวัน)', instruction: 'หาไอเดียทำคลิป YouTube [from_date=2026-07-01, to_date=2026-07-15]', flow: 'youtube_pitch', scope: 'both' },
  NOTEBOOKLM_QUICK_TEMPLATE,
]

export function loadQuickTemplates(): QuickTemplate[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_TEMPLATES
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return DEFAULT_TEMPLATES

    let updated = [...parsed]
    let hasChanged = false

    if (!updated.some((t) => t?.flow === 'notebooklm')) {
      updated.push(NOTEBOOKLM_QUICK_TEMPLATE)
      hasChanged = true
    }
    if (!updated.some((t) => t?.label?.includes('วิเคราะห์หุ้นและดึงข่าว'))) {
      updated.splice(1, 0, EQUITY_NEWS_QUICK_TEMPLATE)
      hasChanged = true
    }
    if (hasChanged) {
      saveQuickTemplates(updated)
      return updated
    }
    return parsed
  } catch {
    return DEFAULT_TEMPLATES
  }
}

export function saveQuickTemplates(templates: QuickTemplate[]): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(templates))
}

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

const DEFAULT_TEMPLATES: QuickTemplate[] = [
  { label: 'วิเคราะห์เศรษฐกิจมหภาค', instruction: 'วิเคราะห์เศรษฐกิจมหภาคและจัดสรรพอร์ตประจำวัน', flow: 'manager', scope: 'both' },
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

    // ผู้ใช้ที่เคย save quick templates ไว้ก่อนมี flow นี้จะไม่เห็น default ใหม่เลย (เพราะ
    // localStorage ไม่ว่างแล้ว โค้ดข้างบนคืนค่าที่ parse ได้ตรงๆ) เติมให้อัตโนมัติครั้งเดียว
    // แบบไม่ทับปุ่มลัดอื่นที่ผู้ใช้ปรับแต่งเอง — เช็คก่อนว่ายังไม่มีถึงจะเติม กัน duplicate ทุกครั้งที่โหลด
    if (!parsed.some((t) => t?.flow === 'notebooklm')) {
      const migrated = [...parsed, NOTEBOOKLM_QUICK_TEMPLATE]
      saveQuickTemplates(migrated)
      return migrated
    }
    return parsed
  } catch {
    return DEFAULT_TEMPLATES
  }
}

export function saveQuickTemplates(templates: QuickTemplate[]): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(templates))
}

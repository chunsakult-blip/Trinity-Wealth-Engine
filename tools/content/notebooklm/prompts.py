"""Parse ## NotebookLM Prompts section จาก Briefing Book markdown กลับเป็น NotebookLMPromptRecord

Section ถูก render จาก tools/content/briefing_renderer.py ในรูปแบบ:
    - [TAG] คำถาม
      *Output Format: รูปแบบคำตอบ*

ไฟล์รุ่นเก่าก่อนมีฟีเจอร์นี้ไม่มี section นี้เลย — extract_notebooklm_prompts คืน list ว่าง ไม่ raise
"""
import re

from core.logger import get_logger
from schemas.briefing_book_schemas import NotebookLMPromptRecord

logger = get_logger(__name__)

_SECTION_HEADER = re.compile(r"^##\s*NotebookLM Prompts\s*$", re.MULTILINE)
_NEXT_HEADER = re.compile(r"^##\s", re.MULTILINE)
_ENTRY_PATTERN = re.compile(
    r"^-\s*\[(?P<type>\w+)\]\s*(?P<question>.+?)\s*\n\s*\*Output Format:\s*(?P<format>.*?)\*\s*$",
    re.MULTILINE,
)
_VALID_TYPES = {"BLIND_SPOT", "SOCRATIC", "FEYNMAN", "RESEARCH"}


def extract_notebooklm_prompts(briefing_text: str) -> list[NotebookLMPromptRecord]:
    """หา section ## NotebookLM Prompts แล้ว parse entry แต่ละอันกลับเป็น record

    คืน list ว่างถ้าไม่พบ section เลย (ไฟล์รุ่นเก่า) — behavior เดิมของ pipeline ทุกประการเมื่อ
    caller ไม่ส่ง prompts มา (with_research=False ตาม default, ไม่มีขั้นตอน notebook_query เพิ่ม)
    """
    header_match = _SECTION_HEADER.search(briefing_text)
    if not header_match:
        return []

    section_text = briefing_text[header_match.end():]
    next_header = _NEXT_HEADER.search(section_text)
    if next_header:
        section_text = section_text[: next_header.start()]

    prompts: list[NotebookLMPromptRecord] = []
    for entry_match in _ENTRY_PATTERN.finditer(section_text):
        ptype = entry_match.group("type").upper()
        if ptype not in _VALID_TYPES:
            logger.warning("ข้าม NotebookLM prompt ที่มี tag ไม่รู้จัก: [%s]", ptype)
            continue
        prompts.append(NotebookLMPromptRecord(
            prompt_id=f"P{len(prompts) + 1:02d}",
            prompt_type=ptype,
            question_or_prompt=entry_match.group("question").strip(),
            expected_output_format=entry_match.group("format").strip(),
        ))
    return prompts


def build_research_query(prompts: list[NotebookLMPromptRecord]) -> str | None:
    """รวม prompt ที่ tag [RESEARCH] ทั้งหมดเป็น query เดียวสำหรับ research_start (รับ query เดียว)
    คืน None ถ้าไม่มี prompt ประเภทนี้เลย — ใช้เป็นสัญญาณเปิด Deep Research อัตโนมัติด้วย
    """
    research_questions = [p.question_or_prompt for p in prompts if p.prompt_type == "RESEARCH"]
    if not research_questions:
        return None
    return "; ".join(research_questions)


def build_notebook_query(prompt: NotebookLMPromptRecord) -> str:
    """ประกอบคำถาม + hint รูปแบบคำตอบที่ต้องการ สำหรับส่งเข้า notebook_query"""
    if prompt.expected_output_format:
        return f"{prompt.question_or_prompt} (ตอบในรูปแบบ: {prompt.expected_output_format})"
    return prompt.question_or_prompt

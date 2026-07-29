"""GET /api/notebooklm/available-sources, POST /api/notebooklm/generate,
GET /api/notebooklm/status/{job_id}

การ์ด NotebookLM สร้างเองโดย user ผ่าน Kanban ปกติ (flow="notebooklm") — ยังไม่ผูกไฟล์ Briefing
Book จนกว่าจะเลือกใน Drawer ครั้งแรก (available-sources endpoint ให้รายชื่อไฟล์มาเลือก) หลังจากนั้น
ไฟล์ที่เลือกจะถูกบันทึกไว้ที่ card.prompt ให้ generate ครั้งถัดไป (retry) ใช้ซ้ำได้โดยไม่ต้องเลือกใหม่

Dispatch ผ่าน app.state.notebooklm_job_queue (durable + single-worker กันรัน notebooklm-mcp
พร้อมกันเกิน 1 process ตาม Account Risk ของ adapter.py) โดยไม่บล็อกคิว Manager/News Funnel/
YouTube Pitch ที่ใช้เวลาสั้นกว่ามาก
"""
import re
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from api import state_db
from api.auth import require_session
from api.schemas import (
    NotebookLMAvailableSourceDTO,
    NotebookLMGenerateRequest,
    NotebookLMGenerateResponse,
    NotebookLMStatusDTO,
)
from tools.content.notebooklm import manifest as manifest_mod
from tools.content.notebooklm.adapter import check_binary_available
from tools.content.notebooklm.models import PreflightError

router = APIRouter(dependencies=[Depends(require_session)])

NOTEBOOKLM_SOURCES_DIR = Path("memories/30_Knowledge_Base/NotebookLM_Sources").resolve()

# ไฟล์ใหม่ (หลัง commit 2dedaf9): {date}_{title}_{suffix_part}_rev{N}_{hash8}_{verified|unverified}.md
# ไฟล์เก่า: {date}_{title}.md เฉยๆ (ไม่มี suffix นี้เลย — เคยเป็น publishable เท่านั้นเพราะ
# unverified-draft feature ยังไม่มีตอนนั้น จึงถือว่า verified=True เสมอ)
_SUFFIX_PATTERN = re.compile(r"_rev\d+_[0-9a-f]{8}_(verified|unverified)$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_source_filename(stem: str) -> tuple[str, str | None, bool]:
    """แยก (title, date_part, is_verified) จากชื่อไฟล์ — รองรับทั้ง format เก่าและใหม่"""
    date_part, sep, rest = stem.partition("_")
    
    if sep and _DATE_PATTERN.match(date_part):
        body = rest
        parsed_date = date_part
    else:
        body = stem
        parsed_date = None

    m = _SUFFIX_PATTERN.search(body)
    if m:
        return body[: m.start()], parsed_date, m.group(1) == "verified"
    return body, parsed_date, True


@router.get("/api/notebooklm/available-sources", response_model=list[NotebookLMAvailableSourceDTO])
def list_available_sources() -> list[NotebookLMAvailableSourceDTO]:
    if not NOTEBOOKLM_SOURCES_DIR.is_dir():
        return []
    result = []
    for p in NOTEBOOKLM_SOURCES_DIR.glob("*.md"):
        title, date_part, is_verified = _parse_source_filename(p.stem)
        result.append(NotebookLMAvailableSourceDTO(file_path=str(p.resolve()), title=title, date_part=date_part, is_verified=is_verified))
    result.sort(key=lambda s: (s.date_part or "", s.title), reverse=True)
    return result


@router.post("/api/notebooklm/generate", response_model=NotebookLMGenerateResponse)
def generate_notebooklm_audio(payload: NotebookLMGenerateRequest, request: Request) -> NotebookLMGenerateResponse:
    with closing(state_db.get_connection()) as conn:
        card = state_db.get_kanban_card(conn, payload.card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="ไม่พบการ์ดนี้")
    if card["flow"] != "notebooklm":
        raise HTTPException(status_code=400, detail="การ์ดนี้ไม่ใช่ NotebookLM Audio Overview")

    briefing_path = card["prompt"] or payload.briefing_file_path
    if not briefing_path:
        raise HTTPException(status_code=400, detail="ต้องเลือกไฟล์ Briefing Book ก่อนสร้าง Audio")

    candidate = Path(briefing_path).resolve()
    if not candidate.is_file() or not candidate.is_relative_to(NOTEBOOKLM_SOURCES_DIR):
        raise HTTPException(
            status_code=400,
            detail="ไฟล์ Briefing Book ที่เลือกไม่ถูกต้อง หรืออยู่นอก NotebookLM_Sources/",
        )

    if card["prompt"] != str(candidate):
        # ครั้งแรกที่เลือกไฟล์ให้การ์ดนี้ — บันทึกไว้ให้ retry ครั้งถัดไปไม่ต้องเลือกซ้ำ
        title, date_part, is_verified = _parse_source_filename(candidate.stem)
        with closing(state_db.get_connection()) as conn:
            state_db.set_kanban_card_source(conn, payload.card_id, str(candidate), is_verified)

    try:
        check_binary_available()
    except PreflightError as e:
        raise HTTPException(status_code=503, detail=str(e))

    job_id = request.app.state.notebooklm_job_queue.dispatch(
        instruction=str(candidate), card_id=payload.card_id, flow="notebooklm",
    )
    with closing(state_db.get_connection()) as conn:
        # ย้ายการ์ดไป executing + ผูก job_id ทันที (เหมือน dispatch_job เดิมใน routes_agents.py)
        # ไม่ต้องรอ worker loop ของ notebooklm_job_queue มาทำแบบ async ทีหลัง
        state_db.move_kanban_card(conn, payload.card_id, "executing", job_id=job_id)
        job = state_db.get_job(conn, job_id)
    return NotebookLMGenerateResponse(job_id=job_id, status=job["status"])


@router.get("/api/notebooklm/status/{job_id}", response_model=NotebookLMStatusDTO)
def get_notebooklm_status(job_id: str) -> NotebookLMStatusDTO:
    with closing(state_db.get_connection()) as conn:
        job = state_db.get_job(conn, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ job_id: {job_id}")

    manifest = None
    try:
        content_hash = manifest_mod.compute_content_hash(Path(job["instruction"]))
        manifest = manifest_mod.load_manifest(manifest_mod.manifest_path_for(content_hash))
    except OSError:
        pass  # ไฟล์ briefing ต้นทางถูกลบไปแล้วหลัง dispatch — ยังคืน job status ได้ตามปกติ

    return NotebookLMStatusDTO(
        job_id=job_id,
        status=job["status"],
        audio_path=manifest.audio_path if manifest else None,
        notebook_id=manifest.notebook_id if manifest else None,
        error=job["error_message"],
    )

"""Run-state manifest สำหรับ NotebookLM Pipeline — เก็บ progress ต่อไฟล์ briefing เพื่อ resume/retry ได้

Location: data/notebooklm_runs/<content_hash>.json
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ValidationError

from core.logger import get_logger
from tools._atomic_io import _atomic_write_to

logger = get_logger(__name__)

MANIFEST_DIR = Path("data/notebooklm_runs")


class NotebookLMManifest(BaseModel):
    """Schema version-controlled manifest — validate ได้ตอนโหลดจากดิสก์

    status ไล่ตามลำดับ: initialized -> notebook_created -> source_added
    -> research_done (optional) -> prompts_queried (optional) -> audio_generating -> completed

    pipeline.py ใช้ "field ไหนถูก populate แล้วบ้าง" เป็นตัวตัดสิน resume point จริง (ไม่ใช่แค่
    อ่าน status string อย่างเดียว) — เมื่อ audio generation ล้มเหลวจริงฝั่ง NotebookLM (ไม่ใช่แค่
    process แครช) status จะถูกย้อนกลับไปที่ checkpoint ก่อนหน้า (research_done/source_added)
    พร้อมเคลียร์ artifact_id แทนที่จะตั้งเป็น "failed" เฉยๆ เพื่อไม่ให้ resume ครั้งถัดไปหลงลืมว่า
    ทำ research ไปแล้วหรือยัง
    """
    schema_version: int = 1
    content_hash: str
    briefing_path: str
    notebook_id: str | None = None
    source_id: str | None = None
    artifact_id: str | None = None
    audio_path: str | None = None
    status: str = "initialized"
    research_task_id: str | None = None
    research_completed: bool = False
    prompts_queried: bool = False
    created_at: str
    updated_at: str


def compute_content_hash(briefing_file_path: Path) -> str:
    """SHA-256 ของเนื้อหาไฟล์ briefing — ใช้เป็น key ของ manifest/resume"""
    return hashlib.sha256(briefing_file_path.read_bytes()).hexdigest()


def manifest_path_for(content_hash: str, *, base_dir: Path | None = None) -> Path:
    """base_dir=None -> ใช้ MANIFEST_DIR ปัจจุบัน (lookup ตอนเรียก ไม่ใช่ตอน def) เพื่อให้ test
    monkeypatch โมดูล-level MANIFEST_DIR แล้วมีผลจริง — ถ้าใส่ default เป็น MANIFEST_DIR ตรงๆ ใน
    signature ค่าจะถูก bind ตอน import ครั้งเดียว monkeypatch ทีหลังจะไม่มีผล
    """
    return (base_dir if base_dir is not None else MANIFEST_DIR) / f"{content_hash}.json"


def load_manifest(path: Path) -> NotebookLMManifest | None:
    """โหลด manifest เดิมถ้ามี — คืน None ถ้าไม่พบไฟล์ หรือไฟล์เสีย/schema ไม่ตรง (ถือว่าเป็นการรันใหม่)"""
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return NotebookLMManifest.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning("Manifest corrupt/schema mismatch ที่ %s (%s) — ถือว่าเริ่มรันใหม่", path, e)
        return None


def save_manifest(manifest: NotebookLMManifest, *, base_dir: Path | None = None) -> Path:
    """เขียน manifest แบบ atomic — คืน path ที่บันทึก"""
    manifest.updated_at = datetime.now(timezone.utc).isoformat()
    path = manifest_path_for(manifest.content_hash, base_dir=base_dir)
    _atomic_write_to(path, manifest.model_dump_json(indent=2))
    return path


def new_manifest(*, content_hash: str, briefing_path: Path) -> NotebookLMManifest:
    now = datetime.now(timezone.utc).isoformat()
    return NotebookLMManifest(
        content_hash=content_hash,
        briefing_path=str(briefing_path),
        created_at=now,
        updated_at=now,
    )

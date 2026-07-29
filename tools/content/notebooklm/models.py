"""Domain types สำหรับ NotebookLM Post-production Pipeline"""
from pathlib import Path

from pydantic import BaseModel


class NotebookLMRunResult(BaseModel):
    """ผลลัพธ์สุดท้ายที่คืนให้ caller — ใช้สำหรับ resume/retry ได้"""
    notebook_id: str
    source_id: str | None = None
    artifact_id: str | None = None
    audio_path: Path | None = None
    status: str
    manifest_path: Path
    content_hash: str


class ConfirmationRequiredError(Exception):
    """Raise เมื่อ pipeline ไปถึงขั้น generate audio โดยไม่มี confirm_generation=True"""


class PreflightError(Exception):
    """Raise เมื่อ preflight check ล้มเหลว (binary ไม่มี, auth ไม่พร้อม, output dir เขียนไม่ได้)"""


class StudioTerminalError(Exception):
    """Raise เมื่อ studio_status คืนสถานะ failed หรือ error ระหว่าง polling"""


class StudioTimeoutError(Exception):
    """Raise เมื่อ polling studio_status เกิน timeout_seconds โดยยังไม่ถึง terminal state"""

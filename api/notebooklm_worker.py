"""run_fn สำหรับ notebooklm_job_queue (แยกจาก api/jobs.py::default_run_fn ที่ผูกกับ LangGraph)

JobQueue._run_job เรียก run_fn ผ่าน `await asyncio.to_thread(self._run_fn, job_id=, thread_id=,
instruction=, flow=, scope=, resume_value=)` — ต้องเป็น sync function รับ kwargs ครบชุดนี้
ถ้าเป็น async def จะได้ coroutine object ที่ไม่มีใคร await เลย (to_thread แค่เรียกฟังก์ชัน ไม่รู้จัก
coroutine) งานจะไม่ถูกรันจริงแต่ขึ้นสถานะ "done" เพราะ thread จบเร็วเกินจริง
"""
import asyncio
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

from api import state_db
from tools.content.notebooklm.pipeline import run_notebooklm_post_production_pipeline
from tools.content.notebooklm.prompts import extract_notebooklm_prompts


def notebooklm_run_fn(
    job_id: str,
    thread_id: str,
    instruction: str,
    flow: str = "notebooklm",
    scope: str = "both",
    resume_value: Optional[dict[str, Any]] = None,
) -> None:
    """instruction คือ briefing_file_path (absolute, resolved แล้วตอน dispatch ใน routes_notebooklm.py)

    อ่าน section ## NotebookLM Prompts จากไฟล์ (ถ้ามี) แล้วส่งเข้า pipeline เอง — ไฟล์ที่มี prompt
    ประเภท [RESEARCH] จะเปิด Deep Research ให้อัตโนมัติ (ดู pipeline.py), ไฟล์รุ่นเก่าที่ไม่มี section
    นี้จะได้ list ว่างและพฤติกรรมเดิมทุกประการ

    ส่ง on_step เข้า pipeline เพื่อเขียน checkpoint หลักลง job_logs — pipeline.py เองไม่รู้จัก
    state_db เลย (tools/ ห้าม import api/ ผิดชั้นสถาปัตยกรรม) จุดนี้จึงเป็นคนตัดสินใจว่าจะเอา
    node/message ไปเขียนที่ไหน ทำให้ LiveTerminal ใน Kanban Drawer มีเนื้อหาจริงให้แสดง
    """
    def _log_step(node: str, message: str) -> None:
        with closing(state_db.get_connection()) as conn:
            state_db.append_job_log(conn, job_id, node, message, role="reply", label=node)

    briefing_path = Path(instruction)
    prompts = extract_notebooklm_prompts(briefing_path.read_text(encoding="utf-8"))
    asyncio.run(run_notebooklm_post_production_pipeline(
        briefing_path, confirm_generation=True, notebooklm_prompts=prompts, on_step=_log_step,
    ))

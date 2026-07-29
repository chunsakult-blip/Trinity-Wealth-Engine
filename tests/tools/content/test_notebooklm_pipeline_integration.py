"""Integration test สำหรับ NotebookLM Pipeline — ใช้บัญชี/quota จริง ห้ามรันใน CI ปกติ

รันเองด้วย: uv run pytest tests/tools/content/test_notebooklm_pipeline_integration.py -m integration

Requires:
- `nlm login` ทำสำเร็จแล้ว (auth_status=configured) — ดู NOTEBOOKLM_AUTH_DIR ใน .env.example
- ยินยอมให้สร้าง Notebook + Audio Overview จริงในบัญชี NotebookLM (มีค่าใช้จ่าย/ใช้ quota จริง)
"""
import os
import shutil
from pathlib import Path

import pytest

from tools.content.notebooklm.pipeline import run_notebooklm_post_production_pipeline

pytestmark = pytest.mark.integration


@pytest.fixture
def sample_briefing_file(tmp_path) -> Path:
    p = tmp_path / "integration_test_briefing.md"
    p.write_text(
        "# Integration Test Briefing\n\n"
        "เนื้อหาทดสอบสั้นๆ สำหรับยืนยันว่า pipeline คุยกับ notebooklm-mcp จริงได้ครบ workflow "
        "(create notebook -> upload -> confirm -> generate audio -> poll -> download).",
        encoding="utf-8",
    )
    return p


@pytest.mark.skip(reason="ใช้บัญชี/quota NotebookLM จริง — สร้าง Notebook + Audio Overview จริง รันมือเท่านั้น")
async def test_full_pipeline_against_real_notebooklm_account(sample_briefing_file):
    if shutil.which("notebooklm-mcp") is None:
        pytest.skip("notebooklm-mcp binary not found in PATH")
    if not os.getenv("NOTEBOOKLM_AUTH_DIR") and not (Path.home() / ".notebooklm").exists():
        pytest.skip("NotebookLM auth ยังไม่ได้ตั้งค่า — รัน `nlm login` ก่อน")
    result = await run_notebooklm_post_production_pipeline(
        sample_briefing_file,
        confirm_generation=True,
        audio_language="th",
        timeout_seconds=1_200,
    )
    assert result.status == "completed"
    assert result.notebook_id
    assert result.audio_path is not None
    assert result.audio_path.exists()
    assert result.audio_path.stat().st_size > 0

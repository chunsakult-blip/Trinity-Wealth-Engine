"""Unit tests สำหรับ api/notebooklm_worker.py — mock run_notebooklm_post_production_pipeline
ทั้งหมด ไม่แตะ notebooklm-mcp จริง (ปิรามิดเดียวกับ test_routes_notebooklm.py)
"""
from contextlib import closing

import pytest

import api.notebooklm_worker as notebooklm_worker
from api import state_db


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBUI_STATE_DB_PATH", str(tmp_path / "webui_state.sqlite"))


@pytest.fixture
def briefing_file(tmp_path):
    p = tmp_path / "test_briefing.md"
    p.write_text("# Test Briefing\n\nเนื้อหาทดสอบ", encoding="utf-8")
    return p


def test_notebooklm_run_fn_passes_extracted_prompts_and_on_step(monkeypatch, briefing_file):
    captured = {}

    async def _fake_pipeline(briefing_path, *, confirm_generation, notebooklm_prompts, on_step):
        captured["briefing_path"] = briefing_path
        captured["confirm_generation"] = confirm_generation
        captured["notebooklm_prompts"] = notebooklm_prompts
        captured["on_step"] = on_step

    monkeypatch.setattr(notebooklm_worker, "run_notebooklm_post_production_pipeline", _fake_pipeline)

    notebooklm_worker.notebooklm_run_fn(
        job_id="job-1", thread_id="thread-1", instruction=str(briefing_file),
    )

    assert captured["briefing_path"] == briefing_file
    assert captured["confirm_generation"] is True
    assert captured["notebooklm_prompts"] == []  # ไฟล์นี้ไม่มี section NotebookLM Prompts
    assert callable(captured["on_step"])


def test_notebooklm_run_fn_on_step_writes_to_job_logs(monkeypatch, briefing_file):
    captured_on_step = {}

    async def _fake_pipeline(briefing_path, *, confirm_generation, notebooklm_prompts, on_step):
        captured_on_step["fn"] = on_step

    monkeypatch.setattr(notebooklm_worker, "run_notebooklm_post_production_pipeline", _fake_pipeline)

    notebooklm_worker.notebooklm_run_fn(
        job_id="job-42", thread_id="thread-1", instruction=str(briefing_file),
    )
    captured_on_step["fn"]("notebook_create", "สร้าง Notebook สำเร็จ")

    with closing(state_db.get_connection()) as conn:
        logs = state_db.get_job_logs_since(conn, "job-42")
    assert len(logs) == 1
    assert logs[0]["node_name"] == "notebook_create"
    assert logs[0]["content"] == "สร้าง Notebook สำเร็จ"


def test_notebooklm_run_fn_extracts_prompts_from_file_with_section(monkeypatch, tmp_path):
    briefing_with_prompts = tmp_path / "with_prompts.md"
    briefing_with_prompts.write_text(
        "# Briefing\n\nเนื้อหา\n\n"
        "## NotebookLM Prompts\n\n"
        "- [SOCRATIC] คำถามทดสอบ\n"
        "  *Output Format: สั้นๆ*\n",
        encoding="utf-8",
    )
    captured = {}

    async def _fake_pipeline(briefing_path, *, confirm_generation, notebooklm_prompts, on_step):
        captured["notebooklm_prompts"] = notebooklm_prompts

    monkeypatch.setattr(notebooklm_worker, "run_notebooklm_post_production_pipeline", _fake_pipeline)

    notebooklm_worker.notebooklm_run_fn(
        job_id="job-2", thread_id="thread-1", instruction=str(briefing_with_prompts),
    )

    assert len(captured["notebooklm_prompts"]) == 1
    assert captured["notebooklm_prompts"][0].prompt_type == "SOCRATIC"

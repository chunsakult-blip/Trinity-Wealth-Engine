"""Tests for agents/news_youtube_flow.py::_save_ingested_content — date prefix + Discord hook"""
from unittest.mock import MagicMock

from agents.news_youtube_flow import _save_ingested_content


class _FakeWriteTool:
    def __init__(self, result: str):
        self.result = result
        self.calls = []

    def invoke(self, args):
        self.calls.append(args)
        return self.result


def test_article_note_gets_date_prefix_in_filename(monkeypatch):
    fake_tool = _FakeWriteTool("บันทึกสำเร็จ (raw, new): /vault/30_Knowledge_Base/News/2026-07-28 หัวข้อข่าว.md")
    monkeypatch.setattr("tools.archivist.writer.write_raw_markdown", fake_tool)
    monkeypatch.setattr("core.discord_notifier.is_discord_enabled", lambda: False)

    content = "---\ntitle: หัวข้อข่าว\nentity_type: article_note\ndate: 2026-07-28\n---\nเนื้อหา"
    _save_ingested_content(content)

    assert fake_tool.calls[0]["filename"] == "2026-07-28 หัวข้อข่าว"
    assert fake_tool.calls[0]["folder_path"] == "30_Knowledge_Base/News"


def test_article_note_sends_discord_notification(monkeypatch):
    fake_tool = _FakeWriteTool("บันทึกสำเร็จ (raw, new): /vault/30_Knowledge_Base/News/2026-07-28 หัวข้อข่าว.md")
    monkeypatch.setattr("tools.archivist.writer.write_raw_markdown", fake_tool)

    sent = {}

    def _fake_send(content, note_path=None):
        sent["content"] = content
        sent["note_path"] = note_path

    monkeypatch.setattr("core.discord_notifier.send_ingested_article_discord", _fake_send)

    content = "---\ntitle: หัวข้อข่าว\nentity_type: article_note\ndate: 2026-07-28\n---\nเนื้อหา"
    _save_ingested_content(content)

    assert sent["content"] == content
    assert sent["note_path"] == "/vault/30_Knowledge_Base/News/2026-07-28 หัวข้อข่าว.md"


def test_youtube_insight_does_not_call_discord(monkeypatch):
    fake_tool = _FakeWriteTool("บันทึกสำเร็จ (raw, new): /vault/30_Knowledge_Base/YouTube_Summaries/2026-07-28 คลิป.md")
    monkeypatch.setattr("tools.archivist.writer.write_raw_markdown", fake_tool)

    send_mock = MagicMock()
    monkeypatch.setattr("core.discord_notifier.send_ingested_article_discord", send_mock)

    content = "---\ntitle: คลิป\nentity_type: youtube_insight\npublished_at: 2026-07-28\n---\nเนื้อหา"
    _save_ingested_content(content)

    send_mock.assert_not_called()


def test_discord_failure_does_not_break_save(monkeypatch):
    """Discord ล้มเหลว (เช่น network error) ต้องไม่ทำให้ save_result หาย — ไฟล์ถูกบันทึกไปแล้วจริง"""
    fake_tool = _FakeWriteTool("บันทึกสำเร็จ (raw, new): /vault/30_Knowledge_Base/News/2026-07-28 หัวข้อข่าว.md")
    monkeypatch.setattr("tools.archivist.writer.write_raw_markdown", fake_tool)

    def _raise(*args, **kwargs):
        raise RuntimeError("Discord ล่ม")

    monkeypatch.setattr("core.discord_notifier.send_ingested_article_discord", _raise)

    content = "---\ntitle: หัวข้อข่าว\nentity_type: article_note\ndate: 2026-07-28\n---\nเนื้อหา"
    result = _save_ingested_content(content)

    assert result == "บันทึกสำเร็จ (raw, new): /vault/30_Knowledge_Base/News/2026-07-28 หัวข้อข่าว.md"

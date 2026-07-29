"""Tests for core/discord_notifier.py — News Funnel Discord webhook notification"""
import json
from unittest.mock import MagicMock

import pytest

from core.discord_notifier import (
    format_news_funnel_embeds,
    is_discord_enabled,
    send_discord_notification,
    send_ingested_article_discord,
    send_synthesized_news_discord,
)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("core.discord_notifier.time.sleep", lambda s: None)


class TestIsDiscordEnabled:
    def test_disabled_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        assert is_discord_enabled() is False

    def test_disabled_when_env_blank(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "   ")
        assert is_discord_enabled() is False

    def test_enabled_when_env_set(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        assert is_discord_enabled() is True


class TestFormatNewsFunnelEmbeds:
    def _event(self, **overrides):
        base = {
            "event_id": "ev-1",
            "canonical_title": "หัวข้อข่าวทดสอบ",
            "comprehensive_summary": "สรุปเนื้อหาข่าวทดสอบ",
            "macro_impact_score": 9,
            "asset_impact_score": 7,
            "canonical_url": "https://example.com/news/1",
        }
        base.update(overrides)
        return base

    def test_builds_embed_with_thai_fields(self):
        embeds = format_news_funnel_embeds([self._event()], period="morning")
        assert len(embeds) == 1
        embed = embeds[0]
        assert "หัวข้อข่าวทดสอบ" in embed["title"]
        assert embed["description"] == "สรุปเนื้อหาข่าวทดสอบ"
        assert embed["url"] == "https://example.com/news/1"
        assert embed["footer"]["text"] == "⏰ รอบ MORNING"
        assert {"name": "Macro Impact", "value": "9/10", "inline": True} in embed["fields"]
        assert {"name": "Asset Impact", "value": "7/10", "inline": True} in embed["fields"]

    def test_color_red_for_score_9_or_above(self):
        embed = format_news_funnel_embeds([self._event(macro_impact_score=9, asset_impact_score=2)])[0]
        assert embed["color"] == 0xFF0000

    def test_color_orange_for_score_8(self):
        embed = format_news_funnel_embeds([self._event(macro_impact_score=8, asset_impact_score=2)])[0]
        assert embed["color"] == 0xFF8C00

    def test_color_yellow_for_score_7(self):
        embed = format_news_funnel_embeds([self._event(macro_impact_score=7, asset_impact_score=2)])[0]
        assert embed["color"] == 0xFFD700

    def test_falls_back_to_links_when_no_canonical_url(self):
        ev = self._event(canonical_url=None, links=["https://example.com/fallback"])
        embed = format_news_funnel_embeds([ev])[0]
        assert embed["url"] == "https://example.com/fallback"

    def test_omits_url_when_no_link_available(self):
        ev = self._event(canonical_url=None, links=[])
        embed = format_news_funnel_embeds([ev])[0]
        assert "url" not in embed

    def test_caps_at_ten_embeds(self):
        events = [self._event(event_id=f"ev-{i}") for i in range(15)]
        embeds = format_news_funnel_embeds(events)
        assert len(embeds) == 10


class TestSendDiscordNotification:
    def test_returns_false_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        assert send_discord_notification([{"title": "x"}]) is False

    def test_returns_true_on_empty_embeds_without_calling_webhook(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        post = MagicMock()
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        assert send_discord_notification([]) is True
        post.assert_not_called()

    def test_returns_true_on_2xx(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        resp = MagicMock(status_code=204)
        monkeypatch.setattr("core.discord_notifier.requests.post", MagicMock(return_value=resp))
        assert send_discord_notification([{"title": "x"}]) is True

    def test_retries_once_on_429_then_succeeds(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        rate_limited = MagicMock(status_code=429)
        rate_limited.json.return_value = {"retry_after": 0.1}
        ok = MagicMock(status_code=204)
        post = MagicMock(side_effect=[rate_limited, ok])
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        assert send_discord_notification([{"title": "x"}]) is True
        assert post.call_count == 2

    def test_gives_up_after_one_retry(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        failing = MagicMock(status_code=500, text="server error")
        post = MagicMock(return_value=failing)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        assert send_discord_notification([{"title": "x"}]) is False
        assert post.call_count == 2

    def test_non_retryable_error_fails_without_retry(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        bad_request = MagicMock(status_code=400, text="bad embed")
        post = MagicMock(return_value=bad_request)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        assert send_discord_notification([{"title": "x"}]) is False
        assert post.call_count == 1

    def test_network_error_retries_then_fails(self, monkeypatch):
        import requests

        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        post = MagicMock(side_effect=requests.exceptions.ConnectionError("refused"))
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        assert send_discord_notification([{"title": "x"}]) is False
        assert post.call_count == 2


class TestSendSynthesizedNewsDiscord:
    def _event(self, note_path, **overrides):
        base = {
            "event_id": "ev-1",
            "canonical_title": "ข่าวสังเคราะห์แล้ว",
            "comprehensive_summary": "สรุปสั้น",
            "macro_impact_score": 8,
            "asset_impact_score": 6,
            "canonical_url": "https://example.com/news/1",
            "synthesized_note_path": str(note_path),
        }
        base.update(overrides)
        return base

    def test_does_nothing_when_not_configured(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        post = MagicMock()
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        note = tmp_path / "note.md"
        note.write_text("# เนื้อหาข่าว", encoding="utf-8")
        send_synthesized_news_discord([self._event(note)])
        post.assert_not_called()

    def test_sends_one_message_per_event_with_file_attached(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        note = tmp_path / "2026-07-28_ข่าว.md"
        note.write_text("## ใจความสำคัญ\n- จุดสำคัญ", encoding="utf-8")
        resp = MagicMock(status_code=204)
        post = MagicMock(return_value=resp)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)

        send_synthesized_news_discord([self._event(note)], period="morning")

        assert post.call_count == 1
        _, kwargs = post.call_args
        assert "files" in kwargs
        filename, file_bytes, content_type = kwargs["files"]["file"]
        assert filename == note.name
        assert file_bytes == note.read_bytes()
        assert content_type == "text/markdown"
        payload = json.loads(kwargs["data"]["payload_json"])
        assert payload["embeds"][0]["title"] == "📰 ข่าวสังเคราะห์แล้ว"

    def test_sends_separate_message_per_event(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        note1 = tmp_path / "a.md"
        note1.write_text("เนื้อหา A", encoding="utf-8")
        note2 = tmp_path / "b.md"
        note2.write_text("เนื้อหา B", encoding="utf-8")
        resp = MagicMock(status_code=204)
        post = MagicMock(return_value=resp)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)

        events = [self._event(note1, event_id="ev-1"), self._event(note2, event_id="ev-2")]
        send_synthesized_news_discord(events)

        assert post.call_count == 2

    def test_skips_event_without_note_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        post = MagicMock()
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        ev = self._event(tmp_path / "unused.md")
        ev["synthesized_note_path"] = None
        send_synthesized_news_discord([ev])
        post.assert_not_called()

    def test_skips_event_when_file_missing_and_continues(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        note2 = tmp_path / "exists.md"
        note2.write_text("เนื้อหา", encoding="utf-8")
        resp = MagicMock(status_code=204)
        post = MagicMock(return_value=resp)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)

        missing_ev = self._event(tmp_path / "does-not-exist.md", event_id="ev-missing")
        ok_ev = self._event(note2, event_id="ev-ok")
        send_synthesized_news_discord([missing_ev, ok_ev])

        assert post.call_count == 1

    def test_one_event_failing_does_not_stop_others(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        note1 = tmp_path / "a.md"
        note1.write_text("A", encoding="utf-8")
        note2 = tmp_path / "b.md"
        note2.write_text("B", encoding="utf-8")
        failing = MagicMock(status_code=400, text="bad request")
        ok = MagicMock(status_code=204)
        post = MagicMock(side_effect=[failing, ok])
        monkeypatch.setattr("core.discord_notifier.requests.post", post)

        events = [self._event(note1, event_id="ev-1"), self._event(note2, event_id="ev-2")]
        send_synthesized_news_discord(events)

        assert post.call_count == 2

    def test_short_content_sent_inline_without_file_attachment(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        note = tmp_path / "note.md"
        note.write_text("เนื้อหาไฟล์จริง — ไม่ควรถูกอ่านเพราะเนื้อหาสั้นพอส่ง inline", encoding="utf-8")
        resp = MagicMock(status_code=204)
        post = MagicMock(return_value=resp)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)

        short_content = "## ใจความสำคัญ\n- จุดที่ 1\n- จุดที่ 2"
        ev = self._event(note, synthesized_content=short_content)
        send_synthesized_news_discord([ev])

        assert post.call_count == 1
        _, kwargs = post.call_args
        assert "files" not in kwargs
        assert kwargs["json"]["embeds"][0]["description"] == short_content

    def test_short_content_strips_impact_banner_before_sending_inline(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        note = tmp_path / "note.md"
        note.write_text("x", encoding="utf-8")
        resp = MagicMock(status_code=204)
        post = MagicMock(return_value=resp)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)

        banner = "> **Macro Impact:** 8/10 | **Asset Impact:** 6/10\n\n"
        body = "## ใจความสำคัญ\n- จุดที่ 1"
        ev = self._event(note, synthesized_content=banner + body)
        send_synthesized_news_discord([ev])

        _, kwargs = post.call_args
        assert kwargs["json"]["embeds"][0]["description"] == body

    def test_long_content_falls_back_to_key_points_section_and_attaches_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        note = tmp_path / "note.md"
        note.write_text("ไฟล์ฉบับเต็มจริงใน Vault", encoding="utf-8")
        resp = MagicMock(status_code=204)
        post = MagicMock(return_value=resp)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)

        key_points = "- จุดสำคัญที่ 1\n- จุดสำคัญที่ 2"
        long_content = (
            f"## ใจความสำคัญ\n{key_points}\n\n"
            "## แนวคิดการลงทุน\n" + ("เนื้อหายาวมาก " * 500)
        )
        ev = self._event(note, synthesized_content=long_content, comprehensive_summary="สรุปสั้นสำรอง")
        send_synthesized_news_discord([ev])

        assert post.call_count == 1
        _, kwargs = post.call_args
        assert "files" in kwargs
        payload = json.loads(kwargs["data"]["payload_json"])
        assert payload["embeds"][0]["description"] == key_points

    def test_long_content_without_key_points_header_falls_back_to_comprehensive_summary(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        note = tmp_path / "note.md"
        note.write_text("ไฟล์ฉบับเต็มจริงใน Vault", encoding="utf-8")
        resp = MagicMock(status_code=204)
        post = MagicMock(return_value=resp)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)

        long_content = "## แนวคิดการลงทุน\n" + ("เนื้อหายาวมาก " * 500)
        ev = self._event(note, synthesized_content=long_content, comprehensive_summary="สรุปสั้นสำรอง")
        send_synthesized_news_discord([ev])

        _, kwargs = post.call_args
        payload = json.loads(kwargs["data"]["payload_json"])
        assert payload["embeds"][0]["description"] == "สรุปสั้นสำรอง"


class TestForumThreadSupport:
    """Forum channel ต้องมี thread_name ทุกครั้ง และถ้าตั้ง required tags ไว้ต้องมี applied_tags ด้วย"""

    def _event(self, note_path, **overrides):
        base = {
            "event_id": "ev-1",
            "canonical_title": "ข่าวสังเคราะห์แล้ว",
            "comprehensive_summary": "สรุปสั้น",
            "macro_impact_score": 8,
            "asset_impact_score": 6,
            "canonical_url": "https://example.com/news/1",
            "synthesized_note_path": str(note_path),
            "synthesized_content": "## ใจความสำคัญ\n- จุดที่ 1",  # สั้นพอส่ง inline เสมอในกลุ่มนี้
        }
        base.update(overrides)
        return base

    def _mock_post(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        resp = MagicMock(status_code=204)
        post = MagicMock(return_value=resp)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        return post

    def test_thread_name_uses_canonical_title(self, tmp_path, monkeypatch):
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        send_synthesized_news_discord([self._event(note, canonical_title="ข่าวทดสอบ Forum")])
        _, kwargs = post.call_args
        assert kwargs["json"]["thread_name"] == "ข่าวทดสอบ Forum"

    def test_thread_name_truncated_to_100_chars(self, tmp_path, monkeypatch):
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        long_title = "ห" * 150
        send_synthesized_news_discord([self._event(note, canonical_title=long_title)])
        _, kwargs = post.call_args
        assert len(kwargs["json"]["thread_name"]) == 100

    def test_thread_name_present_on_attach_file_branch_too(self, tmp_path, monkeypatch):
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        note.write_text("ไฟล์ฉบับเต็ม", encoding="utf-8")
        long_content = "## แนวคิดการลงทุน\n" + ("เนื้อหายาวมาก " * 500)
        send_synthesized_news_discord([self._event(note, synthesized_content=long_content, canonical_title="ข่าวยาว")])
        _, kwargs = post.call_args
        payload = json.loads(kwargs["data"]["payload_json"])
        assert payload["thread_name"] == "ข่าวยาว"

    def test_content_field_has_wrapped_link_from_canonical_url(self, tmp_path, monkeypatch):
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        send_synthesized_news_discord([self._event(note, canonical_url="https://example.com/news/1")])
        _, kwargs = post.call_args
        assert kwargs["json"]["content"] == "🔗 <https://example.com/news/1>"

    def test_content_field_falls_back_to_links_when_no_canonical_url(self, tmp_path, monkeypatch):
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        ev = self._event(note, canonical_url=None, links=["https://example.com/fallback"])
        send_synthesized_news_discord([ev])
        _, kwargs = post.call_args
        assert kwargs["json"]["content"] == "🔗 <https://example.com/fallback>"

    def test_content_field_omitted_when_no_link_available(self, tmp_path, monkeypatch):
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        ev = self._event(note, canonical_url=None, links=[])
        send_synthesized_news_discord([ev])
        _, kwargs = post.call_args
        assert "content" not in kwargs["json"]

    def test_content_field_present_on_attach_file_branch_too(self, tmp_path, monkeypatch):
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        note.write_text("ไฟล์ฉบับเต็ม", encoding="utf-8")
        long_content = "## แนวคิดการลงทุน\n" + ("เนื้อหายาวมาก " * 500)
        send_synthesized_news_discord(
            [self._event(note, synthesized_content=long_content, canonical_url="https://example.com/news/1")]
        )
        _, kwargs = post.call_args
        payload = json.loads(kwargs["data"]["payload_json"])
        assert payload["content"] == "🔗 <https://example.com/news/1>"

    def test_applied_tags_omitted_when_tag_env_vars_not_set(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DISCORD_TAG_ID_ULTRA", raising=False)
        monkeypatch.delenv("DISCORD_TAG_ID_HIGH", raising=False)
        monkeypatch.delenv("DISCORD_TAG_ID_WARNING", raising=False)
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        send_synthesized_news_discord([self._event(note)])
        _, kwargs = post.call_args
        assert "applied_tags" not in kwargs["json"]

    def test_applied_tags_ultra_for_score_9_or_above(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_TAG_ID_ULTRA", "111")
        monkeypatch.setenv("DISCORD_TAG_ID_HIGH", "222")
        monkeypatch.setenv("DISCORD_TAG_ID_WARNING", "333")
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        send_synthesized_news_discord([self._event(note, macro_impact_score=9, asset_impact_score=2)])
        _, kwargs = post.call_args
        assert kwargs["json"]["applied_tags"] == ["111"]

    def test_applied_tags_high_for_score_8(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_TAG_ID_ULTRA", "111")
        monkeypatch.setenv("DISCORD_TAG_ID_HIGH", "222")
        monkeypatch.setenv("DISCORD_TAG_ID_WARNING", "333")
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        send_synthesized_news_discord([self._event(note, macro_impact_score=8, asset_impact_score=2)])
        _, kwargs = post.call_args
        assert kwargs["json"]["applied_tags"] == ["222"]

    def test_applied_tags_warning_for_score_below_8(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_TAG_ID_ULTRA", "111")
        monkeypatch.setenv("DISCORD_TAG_ID_HIGH", "222")
        monkeypatch.setenv("DISCORD_TAG_ID_WARNING", "333")
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        send_synthesized_news_discord([self._event(note, macro_impact_score=7, asset_impact_score=2)])
        _, kwargs = post.call_args
        assert kwargs["json"]["applied_tags"] == ["333"]

    def test_applied_tags_present_on_attach_file_branch_too(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_TAG_ID_ULTRA", "111")
        monkeypatch.setenv("DISCORD_TAG_ID_HIGH", "222")
        monkeypatch.setenv("DISCORD_TAG_ID_WARNING", "333")
        post = self._mock_post(monkeypatch)
        note = tmp_path / "note.md"
        note.write_text("ไฟล์ฉบับเต็ม", encoding="utf-8")
        long_content = "## แนวคิดการลงทุน\n" + ("เนื้อหายาวมาก " * 500)
        send_synthesized_news_discord(
            [self._event(note, synthesized_content=long_content, macro_impact_score=9, asset_impact_score=2)]
        )
        _, kwargs = post.call_args
        payload = json.loads(kwargs["data"]["payload_json"])
        assert payload["applied_tags"] == ["111"]


class TestSendIngestedArticleDiscord:
    """path ดึงข่าวปกติ (news_youtube flow / chat-driven ingest) — ไม่มีคะแนน impact เลย
    ต่างจาก send_synthesized_news_discord: ไม่มี Macro/Asset fields, สีกลาง"""

    def _build_content(self, **overrides):
        from tools.knowledge.core import _build_article_md

        defaults = dict(
            extracted="## ใจความสำคัญ\n- จุดที่ 1\n- จุดที่ 2",
            source_url="https://example.com/article",
            title="บทความทดสอบ",
            today="2026-07-28",
            now_time="2026-07-28 12:00:00",
        )
        defaults.update(overrides)
        return _build_article_md(**defaults)

    def _mock_post(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
        resp = MagicMock(status_code=204)
        post = MagicMock(return_value=resp)
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        return post

    def test_does_nothing_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        post = MagicMock()
        monkeypatch.setattr("core.discord_notifier.requests.post", post)
        send_ingested_article_discord(self._build_content())
        post.assert_not_called()

    def test_short_article_sent_inline_no_score_fields(self, monkeypatch):
        post = self._mock_post(monkeypatch)
        send_ingested_article_discord(self._build_content())

        _, kwargs = post.call_args
        assert "files" not in kwargs
        embed = kwargs["json"]["embeds"][0]
        assert embed["title"] == "📄 บทความทดสอบ"
        assert "## ใจความสำคัญ\n- จุดที่ 1\n- จุดที่ 2" in embed["description"]
        assert embed["url"] == "https://example.com/article"
        assert embed["color"] == 0x5865F2
        assert "fields" not in embed
        assert kwargs["json"]["thread_name"] == "บทความทดสอบ"

    def test_content_field_has_wrapped_source_link(self, monkeypatch):
        post = self._mock_post(monkeypatch)
        send_ingested_article_discord(self._build_content(source_url="https://example.com/article"))
        _, kwargs = post.call_args
        assert kwargs["json"]["content"] == "🔗 <https://example.com/article>"

    def test_content_field_present_on_attach_file_branch_too(self, tmp_path, monkeypatch):
        post = self._mock_post(monkeypatch)
        note = tmp_path / "article.md"
        long_extracted = "## แนวคิดการลงทุน\n" + ("เนื้อหายาวมาก " * 500)
        content = self._build_content(extracted=long_extracted, source_url="https://example.com/article")
        note.write_text(content, encoding="utf-8")
        send_ingested_article_discord(content, note_path=str(note))
        _, kwargs = post.call_args
        payload = json.loads(kwargs["data"]["payload_json"])
        assert payload["content"] == "🔗 <https://example.com/article>"

    def test_frontmatter_wrapper_stripped_from_description(self, monkeypatch):
        post = self._mock_post(monkeypatch)
        send_ingested_article_discord(self._build_content())
        _, kwargs = post.call_args
        description = kwargs["json"]["embeds"][0]["description"]
        assert "---" not in description
        assert "แหล่งที่มา" not in description
        assert "หมายเหตุ" not in description

    def test_long_article_falls_back_to_key_points_and_attaches_file(self, tmp_path, monkeypatch):
        post = self._mock_post(monkeypatch)
        note = tmp_path / "article.md"
        long_extracted = "## ใจความสำคัญ\n- จุดสำคัญ\n\n## แนวคิดการลงทุน\n" + ("เนื้อหายาวมาก " * 500)
        content = self._build_content(extracted=long_extracted)
        note.write_text(content, encoding="utf-8")

        send_ingested_article_discord(content, note_path=str(note))

        _, kwargs = post.call_args
        assert "files" in kwargs
        filename, file_bytes, content_type = kwargs["files"]["file"]
        assert filename == note.name
        assert file_bytes == note.read_bytes()
        payload = json.loads(kwargs["data"]["payload_json"])
        assert payload["embeds"][0]["description"] == "- จุดสำคัญ"

    def test_long_article_without_note_path_skips_send(self, monkeypatch):
        post = self._mock_post(monkeypatch)
        long_extracted = "## แนวคิดการลงทุน\n" + ("เนื้อหายาวมาก " * 500)
        content = self._build_content(extracted=long_extracted)
        send_ingested_article_discord(content, note_path=None)
        post.assert_not_called()

    def test_no_applied_tags_even_when_tag_env_vars_set(self, monkeypatch):
        # ข่าว manual ไม่มีคะแนนให้เลือก tier ของ tag — ไม่ควรใส่ applied_tags เลย
        # ต่างจาก send_synthesized_news_discord ที่เลือก tag ตามคะแนนเสมอ
        monkeypatch.setenv("DISCORD_TAG_ID_ULTRA", "111")
        monkeypatch.setenv("DISCORD_TAG_ID_HIGH", "222")
        monkeypatch.setenv("DISCORD_TAG_ID_WARNING", "333")
        post = self._mock_post(monkeypatch)
        send_ingested_article_discord(self._build_content())
        _, kwargs = post.call_args
        assert "applied_tags" not in kwargs["json"]

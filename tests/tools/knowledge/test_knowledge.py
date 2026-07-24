"""Tests for knowledge_tools pure helpers — no LLM calls"""
import pytest
from pathlib import Path

import tools.knowledge.core as kt_core
import tools.knowledge.article as kt_article

class TestBuildArticleMd:
    def _build(self, **overrides):
        kwargs = dict(
            extracted="## ใจความสำคัญ\n- bullet one",
            source_url="https://example.com/news",
            title="Test Article Title",
            today="2026-01-15",
            now_time="2026-01-15 10:30:00",
        )
        kwargs.update(overrides)
        return kt_core._build_article_md(**kwargs)

    def _parse_frontmatter(self, md_text: str) -> dict:
        import yaml
        parts = md_text.split("---")
        return yaml.safe_load(parts[1]) if len(parts) >= 3 else {}

    def test_starts_with_yaml_frontmatter(self):
        assert self._build().startswith("---\n")

    def test_has_closing_frontmatter_delimiter(self):
        result = self._build()
        parts = result.split("---")
        assert len(parts) >= 3  # ---, frontmatter body, ---, content

    def test_entity_type_article_note(self):
        meta = self._parse_frontmatter(self._build())
        assert meta.get("entity_type") == "article_note"

    def test_source_url_in_frontmatter(self):
        meta = self._parse_frontmatter(self._build(source_url="https://example.com/test"))
        assert meta.get("source_url") == "https://example.com/test"

    def test_date_in_frontmatter(self):
        meta = self._parse_frontmatter(self._build(today="2026-01-15"))
        assert str(meta.get("date")) == "2026-01-15"

    def test_last_updated_in_frontmatter(self):
        meta = self._parse_frontmatter(self._build(now_time="2026-01-15 10:30:00"))
        assert str(meta.get("last_updated")) == "2026-01-15 10:30:00"

    def test_tags_in_frontmatter(self):
        meta = self._parse_frontmatter(self._build())
        assert meta.get("tags") == ["article", "investment_insight"]

    def test_image_line_present_when_provided(self):
        meta = self._parse_frontmatter(self._build(image="https://example.com/og.jpg"))
        assert meta.get("image") == "https://example.com/og.jpg"

    def test_image_line_absent_when_none(self):
        meta = self._parse_frontmatter(self._build(image=None))
        assert "image" not in meta

    def test_colon_in_title_replaced(self):
        result = self._build(title="Breaking: New Insight")
        assert "Breaking - New Insight" in result
        # Original colon should not appear in safe_title
        lines = [l for l in result.split("\n") if l.startswith("title:")]
        assert lines and ":" not in lines[0].split("title: ", 1)[1]

    def test_slash_in_title_replaced(self):
        result = self._build(title="A/B Split Test")
        assert "A-B Split Test" in result

    def test_extracted_content_in_body(self):
        extracted = "## ใจความสำคัญ\n- point one\n- point two"
        assert extracted in self._build(extracted=extracted)

    def test_warning_disclaimer_present(self):
        assert "ตรวจสอบความถูกต้องก่อนนำไปใช้ตัดสินใจลงทุน" in self._build()

    def test_source_url_in_body(self):
        result = self._build(source_url="https://example.com/article")
        assert "> แหล่งที่มา: https://example.com/article" in result

    def test_title_truncated_to_80_chars(self):
        long_title = "a" * 100
        result = kt_core._build_article_md(
            extracted="content",
            source_url="https://x.com",
            title=long_title,
            today="2026-01-01",
            now_time="2026-01-01 00:00:00",
        )
        title_line = next(l for l in result.split("\n") if l.startswith("title:"))
        safe_title = title_line.split("title: ", 1)[1]
        assert len(safe_title) <= 80




"""Unit tests สำหรับ schemas/youtube_pitch_schemas.py"""
import pytest
from pydantic import ValidationError
from schemas.youtube_pitch_schemas import YouTubeContentPitchItem, YouTubeContentPitchBatch


def test_youtube_pitch_item_valid():
    item = YouTubeContentPitchItem(
        pitch_id="uuid-1",
        working_titles=["หัวข้อคำถามเจาะลึก", "หัวข้อวิเคราะห์สมมติฐาน", "หัวข้อเตือนภัยและโอกาส"],
        target_audience="นักลงทุนไทย",
        core_hook="Hook ประโยคเปิดที่น่าสนใจมาก",
        key_questions_to_answer=["คำถาม 1", "คำถาม 2", "คำถาม 3"],
        research_hypotheses=["สมมติฐาน 1", "สมมติฐาน 2"],
        source_event_ids=["ev-1", "ev-2"],
        source_links=["http://example.com/1", "http://example.com/2"],
        source_titles=["ข่าวที่ 1", "ข่าวที่ 2"],
        recommended_format="Deep Dive 15m",
        estimated_impact="ผลกระทบสำคัญต่อตลาดหุ้นไทย",
    )
    assert item.pitch_id == "uuid-1"
    assert len(item.working_titles) == 3


def test_youtube_pitch_item_invalid_working_titles_count():
    # working_titles น้อยกว่าหรือมากกว่า 3 ต้องเกิด ValidationError
    with pytest.raises(ValidationError):
        YouTubeContentPitchItem(
            pitch_id="uuid-2",
            working_titles=["หัวข้อที่ 1", "หัวข้อที่ 2"],  # แค่ 2
            target_audience="นักลงทุนไทย",
            core_hook="Hook",
            key_questions_to_answer=["คำถาม 1", "คำถาม 2", "คำถาม 3"],
            research_hypotheses=["สมมติฐาน 1", "สมมติฐาน 2"],
            source_event_ids=["ev-1"],
            source_links=["http://example.com/1"],
            source_titles=["ข่าวที่ 1"],
            recommended_format="Quick 5m",
            estimated_impact="Impact",
        )

    with pytest.raises(ValidationError):
        YouTubeContentPitchItem(
            pitch_id="uuid-3",
            working_titles=["1", "2", "3", "4"],  # 4 ข้อ
            target_audience="นักลงทุนไทย",
            core_hook="Hook",
            key_questions_to_answer=["คำถาม 1", "คำถาม 2", "คำถาม 3"],
            research_hypotheses=["สมมติฐาน 1", "สมมติฐาน 2"],
            source_event_ids=["ev-1"],
            source_links=["http://example.com/1"],
            source_titles=["ข่าวที่ 1"],
            recommended_format="Quick 5m",
            estimated_impact="Impact",
        )


def test_youtube_pitch_batch_valid():
    item = YouTubeContentPitchItem(
        pitch_id="uuid-1",
        working_titles=["หัวข้อคำถามเจาะลึก", "หัวข้อวิเคราะห์สมมติฐาน", "หัวข้อเตือนภัยและโอกาส"],
        target_audience="นักลงทุนไทย",
        core_hook="Hook",
        key_questions_to_answer=["คำถาม 1", "คำถาม 2", "คำถาม 3"],
        research_hypotheses=["สมมติฐาน 1", "สมมติฐาน 2"],
        source_event_ids=["ev-1"],
        source_links=["http://example.com/1"],
        source_titles=["ข่าวที่ 1"],
        recommended_format="Deep Dive 15m",
        estimated_impact="Impact",
    )
    batch = YouTubeContentPitchBatch(
        pitches=[item],
        date_range_summary="7 วันล่าสุด",
        total_source_events=1,
    )
    assert len(batch.pitches) == 1
    assert batch.total_source_events == 1


def test_youtube_pitch_item_defaults():
    item = YouTubeContentPitchItem(
        pitch_id="uuid-def",
        working_titles=["111", "222", "333"],
        target_audience="aud",
        core_hook="hook",
        key_questions_to_answer=["q1", "q2", "q3"],
        research_hypotheses=["h1", "h2"],
        source_event_ids=["ev-1"],
        source_links=["http://example.com/1"],
        source_titles=["news 1"],
        recommended_format="format",
        estimated_impact="impact",
    )
    assert item.investigation_mode == "mixed"
    assert item.counter_intuitive_lead == ""
    assert item.analogy_generator == ""


def test_validate_generated_pitch_success():
    from schemas.youtube_pitch_schemas import validate_generated_pitch
    item = YouTubeContentPitchItem(
        pitch_id="uuid-val",
        working_titles=["111", "222", "333"],
        target_audience="aud",
        core_hook="hook",
        key_questions_to_answer=["q1", "q2", "q3"],
        research_hypotheses=["h1", "h2"],
        source_event_ids=["ev-1"],
        source_links=["http://example.com/1"],
        source_titles=["news 1"],
        recommended_format="format",
        estimated_impact="impact",
        investigation_mode="stock",
        counter_intuitive_lead="เบาะแสสำคัญค้านสายตา: ตลาดหุ้นเติบโตแต่กระแสเงินสดติดลบ",
        analogy_generator="คำเปรียบเปรย: เหมือนรถที่วิ่งด้วยความเร็วสูงแต่เชื้อเพลิงกำลังจะหมด",
    )
    batch = YouTubeContentPitchBatch(pitches=[item], date_range_summary="summary", total_source_events=1)
    validate_generated_pitch(batch)


def test_validate_generated_pitch_failure_when_empty_or_short():
    from schemas.youtube_pitch_schemas import validate_generated_pitch
    item = YouTubeContentPitchItem(
        pitch_id="uuid-fail",
        working_titles=["111", "222", "333"],
        target_audience="aud",
        core_hook="hook",
        key_questions_to_answer=["q1", "q2", "q3"],
        research_hypotheses=["h1", "h2"],
        source_event_ids=["ev-1"],
        source_links=["http://example.com/1"],
        source_titles=["news 1"],
        recommended_format="format",
        estimated_impact="impact",
        counter_intuitive_lead="สั้นไป",
        analogy_generator="เหมือนรถ",
    )
    batch = YouTubeContentPitchBatch(pitches=[item], date_range_summary="summary", total_source_events=1)
    with pytest.raises(ValueError, match="missing or insufficient counter_intuitive_lead"):
        validate_generated_pitch(batch)

def test_youtube_pitch_item_presentation_style():
    # 1. Default should be narrative
    item_default = YouTubeContentPitchItem(
        pitch_id="uuid-default",
        working_titles=["1", "2", "3"],
        target_audience="aud",
        core_hook="hook",
        key_questions_to_answer=["q1", "q2", "q3"],
        research_hypotheses=["h1", "h2"],
        source_event_ids=["ev-1"],
        source_links=["http://example.com/1"],
        source_titles=["news 1"],
        recommended_format="format",
        estimated_impact="impact",
    )
    assert item_default.presentation_style == "narrative"

    # 2. Should accept interview_qa
    item_qa = YouTubeContentPitchItem(
        pitch_id="uuid-qa",
        working_titles=["1", "2", "3"],
        target_audience="aud",
        core_hook="hook",
        key_questions_to_answer=["q1", "q2", "q3"],
        research_hypotheses=["h1", "h2"],
        source_event_ids=["ev-1"],
        source_links=["http://example.com/1"],
        source_titles=["news 1"],
        recommended_format="format",
        estimated_impact="impact",
        presentation_style="interview_qa"
    )
    assert item_qa.presentation_style == "interview_qa"

    # 3. Should reject invalid literal
    with pytest.raises(ValidationError):
        YouTubeContentPitchItem(
            pitch_id="uuid-invalid",
            working_titles=["1", "2", "3"],
            target_audience="aud",
            core_hook="hook",
            key_questions_to_answer=["q1", "q2", "q3"],
            research_hypotheses=["h1", "h2"],
            source_event_ids=["ev-1"],
            source_links=["http://example.com/1"],
            source_titles=["news 1"],
            recommended_format="format",
            estimated_impact="impact",
            presentation_style="invalid_style"
        )

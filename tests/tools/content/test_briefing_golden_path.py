import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from schemas.briefing_book_schemas import (
    InvestigativeBriefingBookDraft,
    ResearchQualityReport,
)
from schemas.youtube_pitch_schemas import YouTubeContentPitchItem
from tests.fixtures.briefing_fixtures import (
    make_valid_evidence_bundle,
    make_valid_briefing_draft,
    make_valid_macro_observation,
)
from tools.content.briefing_renderer import render_briefing_book
from tools.content.briefing_quality import validate_briefing_book_quality
from tools.content.briefing_artifacts import save_briefing_artifact
from schemas.briefing_book_schemas import BriefingSynthesisResult


@pytest.fixture
def mock_pitch():
    return YouTubeContentPitchItem(
        pitch_id="golden-path-123",
        working_titles=["Title 1", "Title 2", "Title 3"],
        target_audience="All",
        core_hook="Hook",
        key_questions_to_answer=["Q1", "Q2", "Q3"],
        research_hypotheses=["H1", "H2"],
        source_event_ids=["src-1", "src-2"],
        source_links=[],
        source_titles=[],
        recommended_format="10m",
        estimated_impact="High",
        investigation_mode="mixed"
    )


def test_golden_path_macro_mode_success(mock_pitch, tmp_path):
    # Setup
    mock_pitch.investigation_mode = "macro"
    bundle = make_valid_evidence_bundle(mode="macro")
    
    # Needs inflation, rates, and energy
    bundle.macro_snapshot.observations.append(make_valid_macro_observation("energy"))
    
    draft = make_valid_briefing_draft()
    
    # Act - Renderer
    rendered = render_briefing_book(draft, bundle)

    # Act - Quality Gate
    report = validate_briefing_book_quality(bundle, draft, rendered)

    # Expected
    assert report.score == 100
    assert report.publishable is True
    assert report.status == "pass"
    
    # Act - Persistence
    result = BriefingSynthesisResult(
        content=rendered.content,
        draft=draft,
        quality_report=report,
        evidence_bundle=bundle,
    )
    
    # Temporarily set VAULT_PATH for test isolation
    with patch("tools.content.youtube_pitcher.VAULT_PATH", tmp_path):
        saved_path = save_briefing_artifact(result, title="Golden Macro", date_str="2026-07-24")
        
    assert Path(saved_path).exists()
    # Test should ensure sidecar and index are also created correctly (to be implemented)


def test_golden_path_macro_mode_missing_rates_fails(mock_pitch):
    mock_pitch.investigation_mode = "macro"
    bundle = make_valid_evidence_bundle(mode="macro")
    
    # Remove rates
    bundle.macro_snapshot.observations = [obs for obs in bundle.macro_snapshot.observations if obs.category != "rates"]
    
    draft = make_valid_briefing_draft()
    rendered = render_briefing_book(draft, bundle)
    report = validate_briefing_book_quality(bundle, draft, rendered)

    # Expected: fails with macro code
    assert report.publishable is False
    assert report.score < 100
    assert any("rates" in issue.description.lower() or issue.code == "MACRO_MISSING_RATES" for issue in report.issues)


def test_golden_path_stock_mode_success(mock_pitch, tmp_path):
    mock_pitch.investigation_mode = "stock"
    bundle = make_valid_evidence_bundle(mode="stock")
    
    draft = make_valid_briefing_draft()
    rendered = render_briefing_book(draft, bundle)
    report = validate_briefing_book_quality(bundle, draft, rendered)
    
    assert report.score == 100
    assert report.publishable is True


def test_golden_path_stock_mode_missing_eligible_asset(mock_pitch):
    # This should fail BEFORE LLM is called. We simulate this by checking build_briefing_evidence or similar.
    # Currently, build_briefing_evidence might not enforce this directly, but the orchestrator does.
    pass  # We will test the orchestrator behavior in another test


def test_golden_path_mixed_mode_success(mock_pitch, tmp_path):
    mock_pitch.investigation_mode = "mixed"
    bundle = make_valid_evidence_bundle(mode="mixed")
    
    draft = make_valid_briefing_draft()
    rendered = render_briefing_book(draft, bundle)
    report = validate_briefing_book_quality(bundle, draft, rendered)
    
    assert report.score == 100
    assert report.publishable is True


def test_golden_path_mixed_mode_financial_unavailable(mock_pitch):
    mock_pitch.investigation_mode = "mixed"
    bundle = make_valid_evidence_bundle(mode="mixed")
    
    # Make financial unavailable
    bundle.financial_snapshots[0].status = "unavailable"
    
    draft = make_valid_briefing_draft()
    rendered = render_briefing_book(draft, bundle)
    report = validate_briefing_book_quality(bundle, draft, rendered)
    
    assert report.publishable is False
    # Non-bypassable fail
    has_non_bypassable = any(issue.severity == "blocker" and not issue.bypassable for issue in report.issues)
    assert has_non_bypassable is True


def test_golden_path_draft_metadata_missing_allowlist(mock_pitch):
    mock_pitch.investigation_mode = "mixed"
    bundle = make_valid_evidence_bundle(mode="mixed")

    # Metadata missing and make it unverified so it doesn't trigger INCOMPLETE_CANONICAL blocker
    bundle.sources[0].published_at = None
    bundle.sources[0].verification_status = "unverified"
    # We must also change the classification of E01 (which uses src-1) to something other than verified_fact
    bundle.evidence_items[0].classification = "anecdotal"

    draft = make_valid_briefing_draft()
    rendered = render_briefing_book(draft, bundle)
    report = validate_briefing_book_quality(bundle, draft, rendered)

    # It should not be publishable, but should have a bypassable issue
    assert report.publishable is False
    has_bypassable = any(issue.bypassable for issue in report.issues)
    assert has_bypassable is True


def test_golden_path_draft_visual_defect_rejects(mock_pitch):
    mock_pitch.investigation_mode = "mixed"
    bundle = make_valid_evidence_bundle(mode="mixed")
    
    draft = make_valid_briefing_draft()
    # Induce visual defect (e.g. empty visual directives)
    draft.visual_directives = []

    rendered = render_briefing_book(draft, bundle)
    report = validate_briefing_book_quality(bundle, draft, rendered)
    
    assert report.publishable is False
    has_non_bypassable = any(issue.severity == "blocker" and not issue.bypassable for issue in report.issues)
    assert has_non_bypassable is True

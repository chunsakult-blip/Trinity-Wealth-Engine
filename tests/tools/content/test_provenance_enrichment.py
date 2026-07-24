from unittest.mock import MagicMock, patch
import pytest
import socket

from schemas.youtube_pitch_schemas import YouTubeContentPitchItem
from tools.content import provenance_enrichment as provenance

@pytest.fixture(autouse=True)
def mock_dns():
    with patch("socket.getaddrinfo") as mock_getaddr:
        # Mock DNS resolution to return a safe public IP (8.8.8.8)
        mock_getaddr.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 80))]
        yield mock_getaddr


def _pitch() -> YouTubeContentPitchItem:
    return YouTubeContentPitchItem(
        pitch_id="ag-19",
        working_titles=["Oil story", "Oil scenario", "Oil risk"],
        target_audience="Investors",
        core_hook="A source readiness test",
        key_questions_to_answer=["Q1", "Q2", "Q3"],
        research_hypotheses=["H1", "H2"],
        source_event_ids=["ev-1"],
        source_links=["https://example.test/oil"],
        source_titles=["Oil source"],
        recommended_format="15m",
        estimated_impact="High",
    )


def test_refresh_uses_explicit_json_ld_metadata_and_marks_event_verified():
    provenance._CACHE.clear()
    response = MagicMock()
    response.status_code = 200
    response.url = "https://example.test/oil"
    response.text = '''
      <html><head><link rel="canonical" href="/oil-canonical">
      <script type="application/ld+json">{
        "@type":"NewsArticle", "headline":"Oil report",
        "datePublished":"2026-07-23T09:30:00Z",
        "publisher":{"name":"Example News"}
      }</script></head></html>
    '''
    response.encoding = 'utf-8'
    response.raw.read.return_value = response.text.encode('utf-8')
    response.raise_for_status.return_value = None
    event = {"event_id": "ev-1", "title": "Oil source", "links": ["https://example.test/oil"]}

    with patch("tools.content.provenance_enrichment.requests.get", return_value=response) as mock_get:
        refreshed = provenance.refresh_event_provenance(event)
        repeated = provenance.refresh_event_provenance(event)

    assert refreshed["canonical_url"] == "https://example.test/oil-canonical"
    assert refreshed["canonical_publisher"] == "Example News"
    assert refreshed["canonical_published_at"] == "2026-07-23T09:30:00Z"
    assert refreshed["verification_status"] == "verified"
    assert repeated["verification_status"] == "verified"
    assert mock_get.call_count == 1


def test_readiness_blocks_missing_publication_date_without_inventing_one():
    provenance._CACHE.clear()
    response = MagicMock()
    response.status_code = 200
    response.url = "https://example.test/oil"
    response.text = '<meta property="og:site_name" content="Example News">'
    response.encoding = 'utf-8'
    response.raw.read.return_value = response.text.encode('utf-8')
    response.raise_for_status.return_value = None
    with patch("tools.content.provenance_enrichment.requests.get", return_value=response):
        readiness, issues, _, checked = provenance.assess_pitch_source_readiness(
            _pitch(), [{"event_id": "ev-1", "title": "Oil source", "links": ["https://example.test/oil"]}]
        )

    assert readiness == "blocked"
    assert any("วันเผยแพร่" in issue for issue in issues)
    assert checked[0].get("canonical_published_at") is None


def test_verified_legacy_event_is_ready_without_network_call():
    pitch = _pitch().model_copy(update={"source_event_ids": ["ev-1", "ev-2"]})
    first_event = {
        "event_id": "ev-1",
        "title": "Legacy verified story",
        "links": ["https://example.test/oil"],
        "publisher": "Reuters",
        "published_at": "2026-07-23",
        "verification_status": "verified",
    }
    second_event = {
        "event_id": "ev-2",
        "title": "Second verified story",
        "links": ["https://second.example.test/oil"],
        "publisher": "Bloomberg",
        "published_at": "2026-07-23",
        "verification_status": "verified",
    }
    with patch("tools.content.provenance_enrichment.requests.get") as mock_get:
        readiness, issues, _, _ = provenance.assess_pitch_source_readiness(pitch, [first_event, second_event])

    assert readiness == "ready"
    assert issues == []
    mock_get.assert_not_called()


def test_refresh_normalizes_tracking_url_and_reads_time_datetime():
    provenance._CACHE.clear()
    response = MagicMock()
    response.status_code = 200
    response.url = "https://example.test/oil?tsrc=rss"
    response.text = '''
      <meta property="og:site_name" content="Example News">
      <time datetime="2026-07-23T09:30:00Z">23 July</time>
    '''
    response.encoding = 'utf-8'
    response.raw.read.return_value = response.text.encode('utf-8')
    response.raise_for_status.return_value = None

    with patch("tools.content.provenance_enrichment.requests.get", return_value=response) as mock_get:
        refreshed = provenance.refresh_event_provenance({
            "event_id": "ev-time", "links": ["https://example.test/oil?.tsrc=rss&utm_source=feed"],
        })

    assert refreshed["verification_status"] == "verified"
    assert refreshed["canonical_published_at"] == "2026-07-23T09:30:00Z"
    assert refreshed["provenance_recovery_method"] == "page_metadata"
    assert mock_get.call_args.args[0] == "https://example.test/oil"


def test_dated_source_feed_metadata_becomes_verified_without_page_fetch():
    event = {
        "event_id": "ev-feed",
        "links": ["https://example.test/story"],
        "publisher": "Example Feed",
        "published_at": "2026-07-23",
    }
    with patch("tools.content.provenance_enrichment.requests.get") as mock_get:
        refreshed = provenance.refresh_event_provenance(event)

    assert refreshed["verification_status"] == "verified"
    assert refreshed["provenance_recovery_method"] == "source_feed_metadata"
    mock_get.assert_not_called()


def test_prepare_verified_candidate_pool_reports_recovery_statuses():
    candidates = [
        {
            "event_id": "good", "links": ["https://good.example/story"],
            "publisher": "Good News", "published_at": "2026-07-23", "verification_status": "verified",
        },
        {"event_id": "bad", "links": ["https://bad.example/story"]},
    ]
    with patch(
        "tools.content.provenance_enrichment.refresh_selected_event_provenance",
        return_value=[{**candidates[1], "provenance_status": "metadata_missing"}],
    ):
        refreshed, verified, summary = provenance.prepare_verified_candidate_pool(candidates)

    assert len(refreshed) == 2
    assert [item["event_id"] for item in verified] == ["good"]
    assert summary["verified_candidates"] == 1
    assert summary["status_counts"]["metadata_missing"] == 1

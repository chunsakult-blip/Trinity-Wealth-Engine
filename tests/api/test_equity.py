import json
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from api.main import app
from schemas.micro_quant_schemas import MicroQuantOutput

client = TestClient(app)

@pytest.fixture
def auth_cookies():
    return {"session": "mock_session_token"}

@pytest.fixture(autouse=True)
def override_require_session():
    from api.auth import require_session
    app.dependency_overrides[require_session] = lambda: {"user_id": "mock_user"}
    yield
    app.dependency_overrides = {}

def create_mock_sidecar(tmp_vault: Path, ticker: str, date: str, content: dict, is_malformed: bool = False):
    dir_path = tmp_vault / "30_Knowledge_Base/Stocks" / ticker
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{ticker} Equity Analysis {date}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        if is_malformed:
            f.write("{malformed json")
        else:
            json.dump(content, f)
    return file_path

@pytest.fixture
def mock_equity_data():
    return {
        "ticker": "AAPL",
        "market": "US",
        "analysis_date": "2026-08-03",
        "quant_signals": {
            "ticker": "AAPL",
            "market": "US",
            "evaluated_at": "2026-08-03T10:00:00Z"
        },
        "sentiment_context": {
            "evaluated_at": "2026-08-03T10:00:00Z",
            "market_sentiment": "bullish",
            "sources_summary": "Summary"
        },
        "narrative_analysis": "Narrative",
        "base_case_summary": "Base case"
    }

def test_get_latest_equities(equity_tmp_vault, mock_equity_data):
    create_mock_sidecar(Path(equity_tmp_vault), "AAPL", "2026-08-03", mock_equity_data)
    
    response = client.get("/api/equity/latest")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"
    assert data[0]["market"] == "US"
    assert "source_file" in data[0]
    assert "sidecar_file" in data[0]

def test_get_latest_equities_skips_malformed(equity_tmp_vault, mock_equity_data):
    create_mock_sidecar(Path(equity_tmp_vault), "AAPL", "2026-08-03", mock_equity_data)
    create_mock_sidecar(Path(equity_tmp_vault), "MSFT", "2026-08-03", {}, is_malformed=True)
    
    response = client.get("/api/equity/latest")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"

def test_get_latest_equities_multiple_files_tie_breaker(equity_tmp_vault, mock_equity_data):
    # Same filename but different evaluated_at
    mock_old = mock_equity_data.copy()
    mock_old["quant_signals"] = mock_old["quant_signals"].copy()
    mock_old["quant_signals"]["evaluated_at"] = "2026-08-03T09:00:00Z"
    
    mock_new = mock_equity_data.copy()
    mock_new["quant_signals"] = mock_new["quant_signals"].copy()
    mock_new["quant_signals"]["evaluated_at"] = "2026-08-03T10:00:00Z"
    
    # Intentionally naming them differently so the older date has a 'newer' filename alphabetically if it failed to parse date
    create_mock_sidecar(Path(equity_tmp_vault), "AAPL", "2026-08-03-B", mock_old)
    create_mock_sidecar(Path(equity_tmp_vault), "AAPL", "2026-08-03-A", mock_new)
    
    response = client.get("/api/equity/latest")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["evaluated_at"] == "2026-08-03T10:00:00Z"

def test_get_equity_detail_success(equity_tmp_vault, mock_equity_data):
    create_mock_sidecar(Path(equity_tmp_vault), "AAPL", "2026-08-03", mock_equity_data)
    
    response = client.get("/api/equity/aapl") # Test lowercase
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert "quant_signals" in data
    assert "sentiment_context" in data

def test_get_equity_detail_from_model_dump(equity_tmp_vault):
    # Test creating data exactly from MicroQuantOutput to catch nesting issues
    model = MicroQuantOutput(
        ticker="AAPL",
        market="US",
        analysis_date="2026-08-04",
        quant_signals={
            "ticker": "AAPL",
            "market": "US",
            "evaluated_at": "2026-08-04T08:00:00Z",
            "company_name": "Apple Inc",
            "data_quality_flags": ["some_flag"]
        },
        sentiment_context={
            "evaluated_at": "2026-08-04T08:00:00Z",
            "market_sentiment": "bullish",
            "sources_summary": "Test sources"
        },
        narrative_analysis="Test narrative",
        base_case_summary="Test base case"
    )
    dump_data = model.model_dump()
    create_mock_sidecar(Path(equity_tmp_vault), "AAPL", "2026-08-04", dump_data)
    
    response = client.get("/api/equity/aapl")
    assert response.status_code == 200
    data = response.json()
    assert data["company_name"] == "Apple Inc"
    assert "some_flag" in data["data_quality_flags"]

def test_get_equity_detail_not_found(equity_tmp_vault):
    response = client.get("/api/equity/AAPL")
    assert response.status_code == 404

def test_get_equity_detail_invalid_ticker():
    response = client.get("/api/equity/AAPL..")
    assert response.status_code == 400

def test_get_equity_detail_503_on_latest_malformed(equity_tmp_vault, mock_equity_data):
    import copy
    # Create an old valid file
    old_data = copy.deepcopy(mock_equity_data)
    old_data["analysis_date"] = "2026-08-01"
    old_data["quant_signals"]["evaluated_at"] = "2026-08-01T10:00:00Z"
    create_mock_sidecar(Path(equity_tmp_vault), "AAPL", "2026-08-01", old_data)
    # Create a new malformed file
    create_mock_sidecar(Path(equity_tmp_vault), "AAPL", "2026-08-03", {}, is_malformed=True)
    
    response = client.get("/api/equity/AAPL")
    if response.status_code == 200:
        print("RETURNED 200 DATA:", response.json())
    assert response.status_code == 503
    assert "Data corrupted" in response.json()["detail"]

def test_auth_required():
    app.dependency_overrides = {} # Remove mock
    res = client.get("/api/equity/latest")
    assert res.status_code == 401


def test_get_equity_news_not_found(equity_tmp_vault):
    response = client.get("/api/equity/AAPL/news")
    assert response.status_code == 404
    assert "ยังไม่มีข้อมูลข่าว" in response.json()["detail"]


def test_get_equity_news_success_json(equity_tmp_vault):
    stock_dir = Path(equity_tmp_vault) / "30_Knowledge_Base" / "Stocks" / "AAPL"
    stock_dir.mkdir(parents=True, exist_ok=True)
    json_path = stock_dir / "AAPL Latest News 2026-08-05.json"
    news_data = {
        "ticker": "AAPL",
        "market": "US",
        "date": "2026-08-05",
        "last_updated": "2026-08-05 22:10:59",
        "items": [
            {
                "title": "Apple Q3 Earnings Beat",
                "source": "Yahoo Finance",
                "link": "https://example.com/aapl-q3",
                "published_at": "2026-08-05T20:00:00Z",
                "sources_count": 3
            }
        ]
    }
    json_path.write_text(json.dumps(news_data), encoding="utf-8")

    response = client.get("/api/equity/AAPL/news")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Apple Q3 Earnings Beat"


def test_get_equity_news_fallback_md(equity_tmp_vault):
    stock_dir = Path(equity_tmp_vault) / "30_Knowledge_Base" / "Stocks" / "TSLA"
    stock_dir.mkdir(parents=True, exist_ok=True)
    md_path = stock_dir / "TSLA_Latest_News_2026-05-22.md"
    md_content = """---
title: TSLA Latest News 2026-05-22
entity_type: Company_News
ticker: TSLA
market: US
date: 2026-05-22
last_updated: 2026-05-22 10:24:05
---

# ข่าวล่าสุด: TSLA

1. **SpaceX IPO News**
   - ที่มา: Yahoo Finance Video (Reported by 1 sources)
   - อายุข่าว: 5 ชั่วโมง (Fresh)
   - [อ่านต่อ](https://example.com/tsla)
"""
    md_path.write_text(md_content, encoding="utf-8")

    response = client.get("/api/equity/TSLA/news")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "TSLA"
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "SpaceX IPO News"

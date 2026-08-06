import json
from datetime import datetime
import pytest
from pathlib import Path

from schemas.micro_quant_schemas import MicroQuantOutput, QuantSignals, EquitySentimentContext
from tools.market.equity_sidecar import write_equity_sidecar

@pytest.fixture
def mock_output():
    return MicroQuantOutput(
        ticker="aapl", # Test normalization
        market="US",
        analysis_date="2026-08-03",
        quant_signals=QuantSignals(
            ticker="aapl",
            market="US",
            evaluated_at="2026-08-03T10:00:00Z"
        ),
        sentiment_context=EquitySentimentContext(
            evaluated_at="2026-08-03T10:00:00Z",
            market_sentiment="bullish",
            sources_summary="Summary"
        ),
        narrative_analysis="Test narrative",
        base_case_summary="Test base case"
    )

def test_write_equity_sidecar_success(mock_output, tmp_vault, monkeypatch):
    monkeypatch.setattr("tools.market.equity_sidecar.VAULT_PATH", Path(tmp_vault))
    
    write_equity_sidecar(mock_output)
    
    expected_path = Path(tmp_vault) / "30_Knowledge_Base/Stocks/AAPL/AAPL Equity Analysis 2026-08-03.json"
    assert expected_path.exists()
    
    with open(expected_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["ticker"] == "AAPL"
    assert data["market"] == "US"
    assert data["analysis_date"] == "2026-08-03"

def test_write_equity_sidecar_invalid_date(mock_output, tmp_vault, monkeypatch):
    monkeypatch.setattr("tools.market.equity_sidecar.VAULT_PATH", Path(tmp_vault))
    mock_output.analysis_date = "08/03/2026"
    
    with pytest.raises(ValueError, match="Invalid analysis_date format"):
        write_equity_sidecar(mock_output)

def test_write_equity_sidecar_invalid_ticker(mock_output, tmp_vault, monkeypatch):
    monkeypatch.setattr("tools.market.equity_sidecar.VAULT_PATH", Path(tmp_vault))
    mock_output.ticker = "AAPL/../secret"
    
    with pytest.raises(ValueError, match="Invalid ticker format"):
        write_equity_sidecar(mock_output)

def test_write_equity_sidecar_overwrite(mock_output, tmp_vault, monkeypatch):
    monkeypatch.setattr("tools.market.equity_sidecar.VAULT_PATH", Path(tmp_vault))
    
    # Write first time
    write_equity_sidecar(mock_output)
    
    # Write second time with modified data
    mock_output.market = "TH"
    write_equity_sidecar(mock_output)
    
    expected_path = Path(tmp_vault) / "30_Knowledge_Base/Stocks/AAPL/AAPL Equity Analysis 2026-08-03.json"
    
    with open(expected_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["market"] == "TH" # Should be updated

"""Test market_tools: ticker normalization, currency-aware formatting, TH/US market routing"""
import pytest


import tools.market.consensus as consensus



# --- Pure helpers ---




class TestIngestStockConsensusThaiStock:
    def test_th_market_currency(self, mock_yf_ticker):
        result = consensus.ingest_stock_consensus.invoke({"ticker": "PTT", "market": "TH"})
        assert mock_yf_ticker["ticker"] == "PTT.BK"
        assert "45.00 THB" in result  # target mean
        assert "market: TH" in result


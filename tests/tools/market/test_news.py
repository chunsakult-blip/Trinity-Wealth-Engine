"""Test market_tools: ticker normalization, currency-aware formatting, TH/US market routing"""
import pytest


import tools.market.news as news



# --- Pure helpers ---




class TestIngestStockNewsThaiStock:
    def test_th_market_ticker_normalization(self, mock_yf_ticker):
        result = news.ingest_stock_news.invoke({"ticker": "PTT", "market": "TH"})
        assert mock_yf_ticker["ticker"] == "PTT.BK"
        assert "ข่าวล่าสุด: PTT (TH)" in result


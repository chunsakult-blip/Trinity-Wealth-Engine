"""Unit tests สำหรับ tools/market/peer_valuation.py"""
from unittest.mock import patch

from tools.market.peer_valuation import (
    fetch_peer_metrics,
    compute_peer_relative_score,
    _PEER_INFO_CACHE,
    _PEER_INFO_ERROR_CACHE,
)


class TestFetchPeerMetrics:
    def test_unmapped_sector_returns_empty(self):
        assert fetch_peer_metrics(sector="Unmapped Sector XYZ", exclude_ticker="AAPL") == []

    def test_none_sector_returns_empty(self):
        assert fetch_peer_metrics(sector=None, exclude_ticker="AAPL") == []

    @patch("tools.market.peer_valuation._get_peer_info_cached")
    def test_excludes_self_ticker_from_basket(self, mock_info):
        _PEER_INFO_CACHE.clear()
        _PEER_INFO_ERROR_CACHE.clear()
        mock_info.return_value = {"trailingPE": 20.0, "enterpriseToEbitda": 10.0}
        results = fetch_peer_metrics(sector="Technology", exclude_ticker="MSFT")
        symbols = [r["symbol"] for r in results]
        assert "MSFT" not in symbols
        assert "GOOGL" in symbols

    @patch("tools.market.peer_valuation._get_peer_info_cached")
    def test_skips_peer_that_fails_to_fetch_without_erroring_whole_batch(self, mock_info):
        _PEER_INFO_CACHE.clear()
        _PEER_INFO_ERROR_CACHE.clear()

        def side_effect(symbol):
            if symbol == "GOOGL":
                raise RuntimeError("network error")
            return {"trailingPE": 15.0, "enterpriseToEbitda": 8.0}

        mock_info.side_effect = side_effect
        results = fetch_peer_metrics(sector="Technology", exclude_ticker="AAPL")
        symbols = [r["symbol"] for r in results]
        assert "GOOGL" not in symbols
        assert len(results) == len(["MSFT", "GOOGL", "NVDA", "ORCL"]) - 1


class TestComputePeerRelativeScore:
    def test_missing_own_pe_returns_none(self):
        score, delta, count, flag = compute_peer_relative_score(own_pe=None, peer_metrics=[])
        assert score is None
        assert flag == "missing_own_pe:peer_relative"

    def test_negative_own_pe_returns_none(self):
        score, delta, count, flag = compute_peer_relative_score(own_pe=-5.0, peer_metrics=[])
        assert score is None
        assert flag == "missing_own_pe:peer_relative"

    def test_insufficient_valid_peers_returns_none(self):
        peer_metrics = [{"symbol": "MSFT", "pe": 30.0}]  # แค่ 1 ตัว ต่ำกว่าเกณฑ์ขั้นต่ำ 2
        score, delta, count, flag = compute_peer_relative_score(own_pe=25.0, peer_metrics=peer_metrics)
        assert score is None
        assert count == 1
        assert flag == "insufficient_peers:peer_relative"

    def test_cheaper_than_peers_scores_high(self):
        peer_metrics = [{"symbol": "MSFT", "pe": 40.0}, {"symbol": "GOOGL", "pe": 40.0}]
        # own_pe=32, peer_avg=40 -> (32-40)/40*100 = -20% (ถูกกว่า peer 20%) -> best -> 100
        score, delta, count, flag = compute_peer_relative_score(own_pe=32.0, peer_metrics=peer_metrics)
        assert flag is None
        assert delta == -20.0
        assert score == 100.0
        assert count == 2

    def test_more_expensive_than_peers_scores_low(self):
        peer_metrics = [{"symbol": "MSFT", "pe": 20.0}, {"symbol": "GOOGL", "pe": 20.0}]
        # own_pe=30, peer_avg=20 -> +50% -> worst -> 0
        score, delta, count, flag = compute_peer_relative_score(own_pe=30.0, peer_metrics=peer_metrics)
        assert flag is None
        assert delta == 50.0
        assert score == 0.0

    def test_ignores_peers_with_missing_or_invalid_pe(self):
        peer_metrics = [
            {"symbol": "MSFT", "pe": 40.0},
            {"symbol": "GOOGL", "pe": None},
            {"symbol": "NVDA", "pe": -10.0},
            {"symbol": "ORCL", "pe": 40.0},
        ]
        score, delta, count, flag = compute_peer_relative_score(own_pe=40.0, peer_metrics=peer_metrics)
        assert flag is None
        assert count == 2  # เฉพาะ MSFT, ORCL ที่ valid
        assert delta == 0.0  # own_pe เท่ากับ peer_avg พอดี

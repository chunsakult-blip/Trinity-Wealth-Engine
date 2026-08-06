"""Unit tests สำหรับ tools/market/earnings_momentum.py"""
from unittest.mock import MagicMock, patch

import pandas as pd

from tools.market.earnings_momentum import (
    fetch_earnings_revision_data,
    compute_earnings_revision_score,
    _REVISION_CACHE,
    _REVISION_ERROR_CACHE,
)


def _make_revisions_df(up_30d=2, down_30d=0):
    return pd.DataFrame(
        {"upLast7days": [1], "upLast30days": [up_30d], "downLast30days": [down_30d], "downLast7Days": [0]},
        index=["0y"],
    )


def _make_trend_df(current=8.81, ago_30d=8.76):
    return pd.DataFrame({"current": [current], "30daysAgo": [ago_30d]}, index=["0y"])


class TestFetchEarningsRevisionData:
    def setup_method(self):
        _REVISION_CACHE.clear()
        _REVISION_ERROR_CACHE.clear()

    @patch("tools.market.earnings_momentum.yf.Ticker")
    def test_successful_fetch_parses_0y_row(self, mock_ticker_cls):
        mock_tk = MagicMock()
        mock_tk.eps_revisions = _make_revisions_df(up_30d=4, down_30d=1)
        mock_tk.eps_trend = _make_trend_df(current=9.0, ago_30d=8.5)
        mock_ticker_cls.return_value = mock_tk

        data, flag = fetch_earnings_revision_data("AAPL")
        assert flag is None
        assert data["up_last_30d"] == 4
        assert data["down_last_30d"] == 1
        assert data["estimate_current"] == 9.0
        assert data["estimate_30d_ago"] == 8.5

    @patch("tools.market.earnings_momentum.yf.Ticker")
    def test_caches_successful_result(self, mock_ticker_cls):
        mock_tk = MagicMock()
        mock_tk.eps_revisions = _make_revisions_df()
        mock_tk.eps_trend = _make_trend_df()
        mock_ticker_cls.return_value = mock_tk

        fetch_earnings_revision_data("AAPL")
        fetch_earnings_revision_data("AAPL")
        assert mock_ticker_cls.call_count == 1

    @patch("tools.market.earnings_momentum.yf.Ticker")
    def test_missing_0y_row_returns_flag(self, mock_ticker_cls):
        mock_tk = MagicMock()
        mock_tk.eps_revisions = pd.DataFrame({"upLast30days": [1]}, index=["+1q"])  # ไม่มี '0y'
        mock_tk.eps_trend = _make_trend_df()
        mock_ticker_cls.return_value = mock_tk

        data, flag = fetch_earnings_revision_data("NODATA")
        assert data is None
        assert flag == "missing_earnings_revision_data:earnings_momentum"

    @patch("tools.market.earnings_momentum.yf.Ticker")
    def test_empty_dataframe_returns_flag(self, mock_ticker_cls):
        mock_tk = MagicMock()
        mock_tk.eps_revisions = pd.DataFrame()
        mock_tk.eps_trend = pd.DataFrame()
        mock_ticker_cls.return_value = mock_tk

        data, flag = fetch_earnings_revision_data("EMPTY")
        assert data is None
        assert flag == "missing_earnings_revision_data:earnings_momentum"

    @patch("tools.market.earnings_momentum.yf.Ticker")
    def test_exception_returns_fetch_error_flag(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = RuntimeError("boom")
        data, flag = fetch_earnings_revision_data("BROKEN")
        assert data is None
        assert flag == "fetch_error:earnings_momentum"


class TestComputeEarningsRevisionScore:
    def test_none_data_returns_flag(self):
        net, change_pct, score, flag = compute_earnings_revision_score(None)
        assert net is None
        assert score is None
        assert flag == "missing_earnings_revision_data:earnings_momentum"

    def test_positive_estimate_drift_scores_high(self):
        data = {"up_last_30d": 5, "down_last_30d": 0, "estimate_current": 10.5, "estimate_30d_ago": 10.0}
        net, change_pct, score, flag = compute_earnings_revision_score(data)
        assert flag is None
        assert net == 5
        assert change_pct == 5.0
        assert score == 100.0

    def test_negative_estimate_drift_scores_low(self):
        data = {"up_last_30d": 0, "down_last_30d": 3, "estimate_current": 9.5, "estimate_30d_ago": 10.0}
        net, change_pct, score, flag = compute_earnings_revision_score(data)
        assert flag is None
        assert net == -3
        assert change_pct == -5.0
        assert score == 0.0

    def test_zero_base_estimate_guards_division(self):
        data = {"up_last_30d": 1, "down_last_30d": 0, "estimate_current": 1.0, "estimate_30d_ago": 0.0}
        net, change_pct, score, flag = compute_earnings_revision_score(data)
        assert change_pct is None
        assert score is None
        assert flag == "missing_earnings_revision_data:earnings_momentum"
        assert net == 1  # net_revisions ยังคำนวณได้แม้ estimate_change ไม่ได้

    def test_missing_revision_counts_still_computes_change_pct(self):
        data = {"up_last_30d": None, "down_last_30d": None, "estimate_current": 10.5, "estimate_30d_ago": 10.0}
        net, change_pct, score, flag = compute_earnings_revision_score(data)
        assert net is None
        assert change_pct == 5.0
        assert score == 100.0
        assert flag is None

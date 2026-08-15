import csv
import io
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.auth import require_session
from api.main import app
from tools.portfolio.models import Holding, PortfolioState, Summary


@pytest.fixture
def clean_portfolio(isolated_portfolio):
    """Fixture ensuring isolated portfolio directory per test."""
    pt = isolated_portfolio
    post, state = pt._load_or_init("default")
    state.fx_rates["USDTHB"] = 37.0
    state.summary = Summary(total_value_thb=100000.0, total_cost_basis_thb=100000.0)
    cash_thb = Holding(symbol="CASH_THB", asset_type="Cash", units=50000.0)
    cash_usd = Holding(symbol="CASH_USD", asset_type="Cash", units=5000.0)
    state.holdings = [cash_thb, cash_usd]
    pt._save(post, state, "default")
    return pt


def _write_trade_row(
    pt,
    pid: str,
    tx_id: str,
    timestamp: str,
    symbol: str,
    action: str,
    units: float,
    price: float,
    currency: str,
    fx_rate: float | None,
    cost_thb: float,
    realized_pnl: float | None = None,
    notes: str = "",
):
    """Helper to write raw trade ledger row with specified timestamp."""
    from tools.portfolio.constants import _TRADES_LOG_HEADER
    p = pt.trading._get_trades_log_filepath(pid)
    p.parent.mkdir(parents=True, exist_ok=True)
    is_new = not p.exists() or p.stat().st_size == 0
    with open(p, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(_TRADES_LOG_HEADER)
        writer.writerow([
            tx_id,
            timestamp,
            symbol,
            action,
            f"{units:g}",
            f"{price:.4f}",
            currency,
            f"{fx_rate:.4f}" if fx_rate is not None else "",
            f"{cost_thb:.2f}",
            f"{realized_pnl:+.2f}" if realized_pnl is not None else "",
            notes,
        ])


def test_trade_backdate_does_not_corrupt_global_fx_rate(clean_portfolio, monkeypatch):
    """Confirm backdated trade uses historical FX without mutating state.fx_rates['USDTHB']."""
    pt = clean_portfolio
    pid = "default"

    # Mock historical FX returning 34.50 on the isolated prices and trading modules
    monkeypatch.setattr(
        pt.prices,
        "fetch_fx_rate",
        lambda date_str=None, fallback_rate=None: (34.50, "historical"),
    )
    monkeypatch.setattr(
        pt.trading,
        "fetch_fx_rate",
        lambda date_str=None, fallback_rate=None: (34.50, "historical"),
    )
    monkeypatch.setattr(pt.prices, "_fetch_last_price", lambda sym: 150.0)

    state = pt.structured_execute_trade(
        symbol="AAPL",
        asset_type="Stock",
        action="buy",
        units=10,
        price=150.0,
        currency="USD",
        exchange_rate=None,  # left blank -> auto-resolve
        date="2023-01-15",
        portfolio_id=pid,
    )

    # Global FX rate must remain 37.0
    assert state.fx_rates["USDTHB"] == 37.0

    # Trades_Log should record FX_Rate 34.50 and Cost_THB = 10 * 150 * 34.5 = 51750.0
    trades_path = pt.trading._get_trades_log_filepath(pid)
    assert trades_path.exists()
    content = trades_path.read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(content)))
    assert len(rows) >= 2
    header = rows[0]
    trade_row = rows[1]
    fx_idx = header.index("FX_Rate")
    cost_idx = header.index("Cost_THB")
    assert trade_row[fx_idx] == "34.5000"
    assert trade_row[cost_idx] == "51750.00"


def test_fetch_fx_rate_source_reporting(clean_portfolio, monkeypatch):
    """Test fetch_fx_rate returns (rate, source) correctly for historical, live, and fallback."""
    pt = clean_portfolio

    # 1. Historical success
    mock_df = pd.DataFrame(
        {"Close": [34.5]},
        index=pd.to_datetime(["2023-01-15"]),
    )
    monkeypatch.setattr(pt.prices.yf, "download", lambda *args, **kwargs: mock_df)
    rate, source = pt.prices.fetch_fx_rate(date_str="2023-01-15", fallback_rate=36.0)
    assert rate == 34.5
    assert source == "historical"

    # 2. Historical fail -> fallback
    monkeypatch.setattr(pt.prices.yf, "download", lambda *args, **kwargs: None)
    rate, source = pt.prices.fetch_fx_rate(date_str="2023-01-15", fallback_rate=36.0)
    assert rate == 36.0
    assert source == "fallback"

    # 3. Live success
    monkeypatch.setattr(pt.prices, "_fetch_fx_rate", lambda: 36.8)
    rate, source = pt.prices.fetch_fx_rate(date_str=None, fallback_rate=36.0)
    assert rate == 36.8
    assert source == "live"


def test_tz_aware_dividend_index_normalized(clean_portfolio, monkeypatch):
    """Test timezone-aware index from yfinance dividends does not raise TypeError."""
    pt = clean_portfolio
    pid = "default"
    post, state = pt._load_or_init(pid)

    # Add AAPL holding
    aapl = Holding(
        symbol="AAPL",
        asset_type="Stock",
        units=10.0,
        avg_cost_usd=150.0,
        current_price_usd=180.0,
    )
    state.holdings.append(aapl)
    pt._save(post, state, pid)

    # Append BUY trade on 2023-01-01 (prior to 2023-05-10 XD)
    _write_trade_row(
        pt=pt,
        pid=pid,
        tx_id="tx-test-01",
        timestamp="2023-01-01T10:00:00Z",
        symbol="AAPL",
        action="BUY",
        units=10.0,
        price=150.0,
        currency="USD",
        fx_rate=35.0,
        cost_thb=52500.0,
    )

    # Mock yfinance dividends with tz-aware America/New_York DatetimeIndex
    tz_index = pd.date_range("2023-05-10", periods=2, freq="90D", tz="America/New_York")
    mock_div_series = pd.Series([0.24, 0.24], index=tz_index)

    mock_ticker = MagicMock()
    mock_ticker.dividends = mock_div_series
    monkeypatch.setattr(pt.dividends.yf, "Ticker", lambda sym: mock_ticker)

    # Mock batch FX download with tz-aware UTC DatetimeIndex
    fx_index = pd.date_range("2023-01-01", "2024-01-01", freq="D", tz="UTC")
    mock_fx_series = pd.Series(35.0, index=fx_index)
    mock_fx_df = pd.DataFrame({"Close": mock_fx_series})
    monkeypatch.setattr(pt.dividends.yf, "download", lambda *a, **k: mock_fx_df)

    res = pt.sync_dividends_from_history(pid)
    assert res["synced_symbols"] == 1
    assert res["total_rounds"] == 2
    # 10 units * 0.24 * 35.0 * (1 - 0.15) = 71.40 per round -> total 142.80
    assert res["total_dividend_thb"] == 142.80
    assert len(res["details"]["AAPL"]) == 2


def test_sync_narrow_lock_reprotects_concurrent_manual_edit(clean_portfolio, monkeypatch):
    """Confirm TOCTOU re-check during Phase 3 prevents overwriting manual edits made during Phase 2."""
    pt = clean_portfolio
    pid = "default"
    post, state = pt._load_or_init(pid)

    aapl = Holding(
        symbol="AAPL",
        asset_type="Stock",
        units=10.0,
        avg_cost_usd=150.0,
        accumulated_dividend_thb=0.0,
        dividend_source=None,
    )
    state.holdings.append(aapl)
    pt._save(post, state, pid)

    _write_trade_row(
        pt=pt,
        pid=pid,
        tx_id="tx-test-02",
        timestamp="2023-01-01T10:00:00Z",
        symbol="AAPL",
        action="BUY",
        units=10.0,
        price=150.0,
        currency="USD",
        fx_rate=35.0,
        cost_thb=52500.0,
    )

    tz_index = pd.date_range("2023-05-10", periods=1, freq="90D")
    mock_div_series = pd.Series([1.0], index=tz_index)
    mock_ticker = MagicMock()
    mock_ticker.dividends = mock_div_series
    monkeypatch.setattr(pt.dividends.yf, "Ticker", lambda sym: mock_ticker)
    monkeypatch.setattr(pt.dividends, "_fetch_batch_fx", lambda *a, **k: None)

    # Hook into Phase 2 calculation to simulate concurrent edit
    original_calc = pt.dividends._calculate_symbol_dividends

    def concurrent_edit_during_calc(*args, **kwargs):
        # Simulate another request editing AAPL to manual
        p, s = pt._load_or_init(pid)
        target = pt._find_holding(s, "AAPL")
        target.accumulated_dividend_thb = 999.0
        target.dividend_source = "manual"
        pt._save(p, s, pid)
        return original_calc(*args, **kwargs)

    monkeypatch.setattr(pt.dividends, "_calculate_symbol_dividends", concurrent_edit_during_calc)

    res = pt.sync_dividends_from_history(pid)

    # AAPL must be skipped and placed in skipped_manual
    assert "AAPL" in res["skipped_manual"]
    assert res["synced_symbols"] == 0

    # Holding must retain manual value 999.0
    _, final_state = pt._load_or_init(pid)
    final_aapl = pt._find_holding(final_state, "AAPL")
    assert final_aapl.accumulated_dividend_thb == 999.0
    assert final_aapl.dividend_source == "manual"


def test_batch_fx_lookup_and_asof(clean_portfolio):
    """Verify _get_fx_at_date properly resolves dates using .asof() in memory."""
    pt = clean_portfolio
    fx_dates = pd.to_datetime(["2023-05-08", "2023-05-09", "2023-05-10", "2023-05-12"])
    fx_series = pd.Series([34.1, 34.2, 34.3, 34.5], index=fx_dates)

    # Exact date
    rate1 = pt.dividends._get_fx_at_date(fx_series, date(2023, 5, 10), 36.0)
    assert rate1 == 34.3

    # Weekend date (May 11 -> asof May 10)
    rate2 = pt.dividends._get_fx_at_date(fx_series, date(2023, 5, 11), 36.0)
    assert rate2 == 34.3

    # Before earliest -> fallback
    rate3 = pt.dividends._get_fx_at_date(fx_series, date(2023, 5, 1), 36.0)
    assert rate3 == 36.0


def test_thai_stock_tax_and_symbol(clean_portfolio, monkeypatch):
    """Verify Thai stocks (THB) use 10% tax rate and query with .BK."""
    pt = clean_portfolio
    pid = "default"
    post, state = pt._load_or_init(pid)

    ptt = Holding(
        symbol="PTT",
        asset_type="Stock",
        units=1000.0,
        avg_cost_thb=35.0,
        current_price_thb=36.0,
    )
    state.holdings.append(ptt)
    pt._save(post, state, pid)

    _write_trade_row(
        pt=pt,
        pid=pid,
        tx_id="tx-test-03",
        timestamp="2023-01-01T10:00:00Z",
        symbol="PTT",
        action="BUY",
        units=1000.0,
        price=35.0,
        currency="THB",
        fx_rate=None,
        cost_thb=35000.0,
    )

    tz_index = pd.date_range("2023-09-01", periods=1, freq="D")
    mock_div_series = pd.Series([2.0], index=tz_index)

    mock_ticker = MagicMock()
    mock_ticker.dividends = mock_div_series
    queried_symbols = []

    def mock_ticker_call(sym):
        queried_symbols.append(sym)
        return mock_ticker

    monkeypatch.setattr(pt.dividends.yf, "Ticker", mock_ticker_call)
    monkeypatch.setattr(pt.dividends, "_fetch_batch_fx", lambda *a, **k: None)

    res = pt.sync_dividends_from_history(pid)
    assert "PTT.BK" in queried_symbols
    assert res["synced_symbols"] == 1
    # 1000 units * 2.0 THB * (1 - 0.10 tax) = 1800.0 THB
    assert res["total_dividend_thb"] == 1800.0
    assert res["details"]["PTT"][0]["tax_rate"] == 0.10


def test_anti_drift_summary(clean_portfolio, monkeypatch):
    """Verify state.summary.total_accumulated_dividend equals sum of holdings accumulated dividends."""
    pt = clean_portfolio
    pid = "default"
    post, state = pt._load_or_init(pid)

    # Reset holdings to just H1 and H2 for clean isolated verification
    h1 = Holding(symbol="H1", asset_type="Stock", units=10.0, avg_cost_thb=100.0)
    h2 = Holding(symbol="H2", asset_type="Stock", units=10.0, avg_cost_thb=100.0)
    state.holdings = [h1, h2]
    pt._save(post, state, pid)

    _write_trade_row(pt, pid, "tx-h1", "2023-01-01T10:00:00Z", "H1", "BUY", 10.0, 100.0, "THB", None, 1000.0)
    _write_trade_row(pt, pid, "tx-h2", "2023-01-01T10:00:00Z", "H2", "BUY", 10.0, 100.0, "THB", None, 1000.0)

    tz_index = pd.date_range("2023-09-01", periods=1, freq="D")
    mock_div_series = pd.Series([5.0], index=tz_index)
    mock_ticker = MagicMock()
    mock_ticker.dividends = mock_div_series
    monkeypatch.setattr(pt.dividends.yf, "Ticker", lambda sym: mock_ticker)
    monkeypatch.setattr(pt.dividends, "_fetch_batch_fx", lambda *a, **k: None)

    res = pt.sync_dividends_from_history(pid)
    _, final_state = pt._load_or_init(pid)
    expected_sum = sum(h.accumulated_dividend_thb or 0.0 for h in final_state.holdings)
    assert final_state.summary.total_accumulated_dividend == expected_sum
    assert final_state.summary.total_accumulated_dividend == res["total_dividend_thb"]


def test_received_vs_upcoming_partitioning(clean_portfolio, monkeypatch):
    """Confirm rounds with future pay_date are categorized as upcoming and excluded from accumulated_dividend_thb."""
    pt = clean_portfolio
    pid = "default"
    post, state = pt._load_or_init(pid)

    pg = Holding(
        symbol="PG",
        asset_type="Stock",
        units=2.0,
        avg_cost_usd=140.0,
    )
    state.holdings.append(pg)
    pt._save(post, state, pid)

    _write_trade_row(
        pt=pt,
        pid=pid,
        tx_id="tx-pg-buy",
        timestamp="2025-01-01T10:00:00Z",
        symbol="PG",
        action="BUY",
        units=2.0,
        price=140.0,
        currency="USD",
        fx_rate=35.0,
        cost_thb=9800.0,
    )

    # 2 rounds:
    # 1. 100 days ago (Ex-Date past, Pay Date past) -> Received
    # 2. 10 days ago (Ex-Date past, Pay Date 5 days in future) -> Upcoming
    d1 = date.today() - timedelta(days=100)
    d2 = date.today() - timedelta(days=10)
    future_pay_date = date.today() + timedelta(days=5)

    dates = pd.to_datetime([d1.isoformat(), d2.isoformat()])
    mock_div_series = pd.Series([1.0, 1.0], index=dates)

    mock_ticker = MagicMock()
    mock_ticker.dividends = mock_div_series
    mock_ticker.calendar = {"Dividend Date": future_pay_date, "Ex-Dividend Date": d2}
    monkeypatch.setattr(pt.dividends.yf, "Ticker", lambda sym: mock_ticker)
    monkeypatch.setattr(pt.dividends, "_fetch_batch_fx", lambda *a, **k: None)

    res = pt.sync_dividends_from_history(pid)
    assert res["total_rounds"] == 2
    assert res["total_received_rounds"] == 1
    assert res["total_upcoming_rounds"] == 1

    # Round 1: 2.0 units * 1.0 * 37.0 * 0.85 = 62.90 THB ($1.70 native)
    assert res["total_dividend_thb"] == 62.90
    assert res["total_upcoming_thb"] == 62.90

    _, final_state = pt._load_or_init(pid)
    final_pg = pt._find_holding(final_state, "PG")
    assert final_pg.accumulated_dividend_thb == 62.90
    assert final_pg.accumulated_dividend_native == 1.70
    assert final_pg.upcoming_dividend_thb == 62.90
    assert final_pg.upcoming_dividend_native == 1.70
    assert len(final_pg.dividend_rounds) == 2
    assert final_pg.dividend_rounds[0].status == "upcoming"  # latest first
    assert final_pg.dividend_rounds[1].status == "received"

    # State summary total_accumulated_dividend must only include received 62.90
    assert final_state.summary.total_accumulated_dividend == 62.90


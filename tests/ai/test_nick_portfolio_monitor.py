from ai.nick.portfolio_monitor import NickPortfolioMonitor


def test_daily_history_has_value_series_and_trade_log():
    monitor = NickPortfolioMonitor()
    history = monitor.simulate_daily_history(
        selected_symbols=["AAPL", "MSFT", "NVDA"],
        starting_cash_thb=1_000_000.0,
        prices_by_day={
            "2026-08-17": {"AAPL": 200.0, "MSFT": 450.0, "NVDA": 110.0},
            "2026-08-18": {"AAPL": 210.0, "MSFT": 470.0, "NVDA": 118.0},
            "2026-08-19": {"AAPL": 220.0, "MSFT": 500.0, "NVDA": 130.0},
        },
        profit_target_pct=0.10,
        stop_loss_pct=-0.15,
    )

    assert len(history["daily_series"]) >= 3
    assert history["daily_series"][-1]["portfolio_value_thb"] > 0
    assert history["trade_log"][0]["action"] == "BUY"


def test_live_snapshot_includes_symbol_and_benchmark_prices():
    monitor = NickPortfolioMonitor()
    snapshot = monitor.build_live_snapshot(
        price_map={"AAPL": 220.0, "MSFT": 500.0, "NVDA": 130.0, "SPY": 770.0},
        selected_symbols=["AAPL", "MSFT", "NVDA"],
    )

    assert snapshot["benchmark"]["symbol"] == "SPY"
    assert snapshot["positions"][0]["symbol"] == "AAPL"
    assert snapshot["portfolio_value_thb"] > 0

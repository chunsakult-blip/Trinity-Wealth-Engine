from ai.nick.auto_portfolio import NickAutoPortfolioSimulator


def test_auto_portfolio_buys_selected_symbols_and_keeps_cash_cap():
    simulator = NickAutoPortfolioSimulator()
    trade_plan = simulator.build_trade_plan(
        cash_thb=1_000_000.0,
        selected_symbols=["AAPL", "MSFT", "NVDA"],
        price_map={"AAPL": 210.0, "MSFT": 480.0, "NVDA": 120.0},
    )

    assert len(trade_plan) == 3
    assert sum(item["cost_thb"] for item in trade_plan) <= 1_000_000.0 + 1e-9
    assert all(item["symbol"] in {"AAPL", "MSFT", "NVDA"} for item in trade_plan)


def test_auto_portfolio_sells_when_profit_target_is_hit():
    simulator = NickAutoPortfolioSimulator()
    result = simulator.simulate_daily_run(
        symbols=["MSFT"],
        starting_cash_thb=1_000_000.0,
        prices_by_day={
            "2026-08-19": {"MSFT": 480.0},
            "2026-08-20": {"MSFT": 520.0},
            "2026-08-21": {"MSFT": 560.0},
        },
        target_profit_pct=0.12,
    )

    assert result[0]["buy_total_thb"] > 0
    assert any(item["action"] == "SELL" for item in result[1:])

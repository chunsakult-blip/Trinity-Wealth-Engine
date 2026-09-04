from ai.nick.portfolio_rebalance import PortfolioRebalanceEngine


def _target():
    return {
        "positions": [
            {
                "ticker": "AAPL",
                "allocation": 30.0,
            },
            {
                "ticker": "MSFT",
                "allocation": 25.0,
            },
            {
                "ticker": "NVDA",
                "allocation": 25.0,
            },
        ],
        "cash_weight": 20.0,
    }


def test_rebalance_builds_buy_and_sell_actions():
    current = {
        "positions": [
            {
                "ticker": "AAPL",
                "allocation": 20.0,
            },
            {
                "ticker": "MSFT",
                "allocation": 30.0,
            },
            {
                "ticker": "TSLA",
                "allocation": 10.0,
            },
        ]
    }

    result = PortfolioRebalanceEngine().build_plan(
        _target(),
        current,
    )

    assert result.status == "rebalance_required"

    actions = {item.ticker: item for item in result.actions}

    assert actions["AAPL"].action == "BUY"
    assert actions["AAPL"].delta_weight == 10.0

    assert actions["MSFT"].action == "SELL"
    assert actions["MSFT"].delta_weight == -5.0

    assert actions["NVDA"].action == "BUY"
    assert actions["NVDA"].delta_weight == 25.0

    assert actions["TSLA"].action == "SELL"
    assert actions["TSLA"].delta_weight == -10.0


def test_rebalance_detects_balanced_portfolio():
    target = _target()

    current = {
        "positions": [
            {"ticker": "AAPL", "allocation": 30.0},
            {"ticker": "MSFT", "allocation": 25.0},
            {"ticker": "NVDA", "allocation": 25.0},
        ]
    }

    result = PortfolioRebalanceEngine().build_plan(
        target,
        current,
    )

    assert result.status == "balanced"
    assert result.actions == []


def test_rebalance_ignores_small_deltas():
    target = _target()

    current = {
        "positions": [
            {"ticker": "AAPL", "allocation": 30.4},
            {"ticker": "MSFT", "allocation": 25.0},
            {"ticker": "NVDA", "allocation": 25.0},
        ]
    }

    result = PortfolioRebalanceEngine().build_plan(
        target,
        current,
        min_delta=1.0,
    )

    assert result.status == "balanced"
    assert result.actions == []
    assert result.unchanged_count == 3


def test_rebalance_handles_missing_current_portfolio():
    result = PortfolioRebalanceEngine().build_plan(
        _target(),
        None,
    )

    assert result.status == "no_current_portfolio"
    assert result.actions == []

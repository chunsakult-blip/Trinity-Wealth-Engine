from ai.nick.portfolio_risk_guard import PortfolioRiskGuard


def test_portfolio_risk_guard_passes_safe_portfolio():
    guard = PortfolioRiskGuard(
        max_position=20.0,
        min_cash=20.0,
        max_risk_exposure=45.0,
    )

    result = guard.validate({
        "positions": [
            {"ticker": "AAPL", "allocation": 20.0, "risk_score": 10},
            {"ticker": "MSFT", "allocation": 20.0, "risk_score": 15},
        ],
        "cash_weight": 60.0,
    })

    assert result.approved is True
    assert result.status == "passed"
    assert result.cash_weight == 60.0


def test_portfolio_risk_guard_blocks_position_over_cap():
    guard = PortfolioRiskGuard(max_position=20.0)

    result = guard.validate({
        "positions": [
            {"ticker": "AAPL", "allocation": 25.0, "risk_score": 10},
        ],
    })

    assert result.approved is False
    assert result.checks["position_cap"] is False


def test_portfolio_risk_guard_blocks_insufficient_cash():
    guard = PortfolioRiskGuard(
        max_position=40.0,
        min_cash=20.0,
    )

    result = guard.validate({
        "positions": [
            {"ticker": "AAPL", "allocation": 40.0},
            {"ticker": "MSFT", "allocation": 40.0},
            {"ticker": "NVDA", "allocation": 25.0},
        ],
    })

    assert result.approved is False
    assert result.checks["minimum_cash"] is False


def test_portfolio_risk_guard_blocks_excessive_risk():
    guard = PortfolioRiskGuard(
        max_position=50.0,
        min_cash=20.0,
        max_risk_exposure=20.0,
    )

    result = guard.validate({
        "positions": [
            {"ticker": "RISKY1", "allocation": 40.0, "risk_score": 80},
            {"ticker": "RISKY2", "allocation": 30.0, "risk_score": 80},
        ],
    })

    assert result.approved is False
    assert result.checks["risk_exposure"] is False
    assert result.risk_exposure == 56.0


def test_portfolio_risk_guard_blocks_duplicate_ticker():
    guard = PortfolioRiskGuard()

    result = guard.validate({
        "positions": [
            {"ticker": "AAPL", "allocation": 10.0},
            {"ticker": "AAPL", "allocation": 10.0},
        ],
    })

    assert result.approved is False
    assert result.checks["duplicate_tickers"] is False

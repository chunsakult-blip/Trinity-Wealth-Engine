from ai.nick.portfolio_monitoring import PortfolioMonitoringEngine


def _target():
    return {
        "positions": [
            {"ticker": "AAPL", "allocation": 30.0},
            {"ticker": "MSFT", "allocation": 25.0},
            {"ticker": "NVDA", "allocation": 25.0},
        ],
        "cash_weight": 20.0,
        "risk_guard": {
            "approved": True,
            "risk_exposure": 30.0,
        },
        "quality": {
            "score": 85.0,
        },
    }


def test_monitor_reports_healthy_portfolio():
    current = {
        "positions": [
            {"ticker": "AAPL", "allocation": 29.0},
            {"ticker": "MSFT", "allocation": 25.0},
            {"ticker": "NVDA", "allocation": 26.0},
        ],
        "cash_weight": 20.0,
    }

    result = PortfolioMonitoringEngine().evaluate(
        _target(),
        current,
    )

    assert result.status == "healthy"
    assert result.allocation_drift == 1.0
    assert result.cash_drift == 0.0
    assert result.risk_exposure == 30.0
    assert not result.alerts
    assert all(result.checks.values())


def test_monitor_detects_allocation_drift():
    current = {
        "positions": [
            {"ticker": "AAPL", "allocation": 15.0},
            {"ticker": "MSFT", "allocation": 25.0},
            {"ticker": "NVDA", "allocation": 25.0},
        ],
        "cash_weight": 35.0,
    }

    result = PortfolioMonitoringEngine().evaluate(
        _target(),
        current,
        max_allocation_drift=5.0,
    )

    assert result.status == "attention"
    assert result.allocation_drift == 15.0
    assert result.cash_drift == 15.0
    assert result.checks["allocation_drift"] is False
    assert any("Allocation drift" in alert for alert in result.alerts)


def test_monitor_detects_risk_and_cash_alerts():
    target = _target()
    target["risk_guard"] = {
        "approved": True,
        "risk_exposure": 60.0,
    }

    current = {
        "positions": [
            {"ticker": "AAPL", "allocation": 30.0},
            {"ticker": "MSFT", "allocation": 25.0},
            {"ticker": "NVDA", "allocation": 25.0},
        ],
        "cash_weight": 10.0,
    }

    result = PortfolioMonitoringEngine().evaluate(
        target,
        current,
    )

    assert result.status == "attention"
    assert result.checks["cash"] is False
    assert result.checks["risk_exposure"] is False
    assert len(result.alerts) >= 2


def test_monitor_without_current_portfolio_is_snapshot_only():
    result = PortfolioMonitoringEngine().evaluate(_target())

    assert result.status == "healthy"
    assert result.allocation_drift == 0.0
    assert result.cash_drift == 0.0
    assert result.checks["allocation_drift"] is True


def test_monitor_detects_blocked_risk_guard():
    target = _target()
    target["risk_guard"] = {
        "approved": False,
        "risk_exposure": 50.0,
    }

    result = PortfolioMonitoringEngine().evaluate(target)

    assert result.status == "attention"
    assert result.checks["risk_guard"] is False
    assert any("risk guard" in alert.lower() for alert in result.alerts)

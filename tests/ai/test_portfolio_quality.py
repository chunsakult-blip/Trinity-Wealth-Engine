from ai.nick.portfolio_quality import PortfolioQualityEngine


def test_portfolio_quality_approves_strong_portfolio():
    portfolio = {
        "cash_weight": 20.0,
        "total_invested": 80.0,
        "positions": [
            {
                "ticker": "AAPL",
                "score": 90.0,
                "risk_score": 10.0,
                "allocation": 20.0,
            },
            {
                "ticker": "MSFT",
                "score": 85.0,
                "risk_score": 15.0,
                "allocation": 20.0,
            },
            {
                "ticker": "NVDA",
                "score": 80.0,
                "risk_score": 25.0,
                "allocation": 20.0,
            },
        ],
        "risk_guard": {
            "approved": True,
            "risk_exposure": 10.0,
        },
    }

    result = PortfolioQualityEngine().evaluate(portfolio)

    assert result.decision == "APPROVE"
    assert result.score >= 80.0
    assert result.investment_quality > 80.0
    assert result.risk_quality >= 70.0


def test_portfolio_quality_rejects_blocked_portfolio():
    portfolio = {
        "cash_weight": 20.0,
        "total_invested": 60.0,
        "positions": [
            {
                "ticker": "RISKY1",
                "score": 95.0,
                "risk_score": 90.0,
                "allocation": 20.0,
            },
            {
                "ticker": "RISKY2",
                "score": 90.0,
                "risk_score": 90.0,
                "allocation": 20.0,
            },
            {
                "ticker": "RISKY3",
                "score": 85.0,
                "risk_score": 90.0,
                "allocation": 20.0,
            },
        ],
        "risk_guard": {
            "approved": False,
            "risk_exposure": 54.0,
        },
    }

    result = PortfolioQualityEngine().evaluate(portfolio)

    assert result.decision == "REJECT"
    assert result.score < 80.0
    assert result.reasons
    assert "risk guard" in result.reasons[0].lower()


def test_portfolio_quality_handles_empty_portfolio():
    result = PortfolioQualityEngine().evaluate(
        {
            "cash_weight": 100.0,
            "total_invested": 0.0,
            "positions": [],
            "risk_guard": {
                "approved": True,
                "risk_exposure": 0.0,
            },
        }
    )

    assert result.score == 0.0
    assert result.decision == "HOLD_CASH"
    assert "No portfolio positions" in result.reasons[0]

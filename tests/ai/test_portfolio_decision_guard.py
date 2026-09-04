from ai.nick.portfolio_decision_guard import PortfolioDecisionGuard


def test_portfolio_decision_guard_approves_strong_portfolio():
    portfolio = {
        "quality": {
            "score": 86.0,
            "decision": "APPROVE",
        },
        "risk_guard": {
            "approved": True,
        },
    }

    result = PortfolioDecisionGuard().decide(
        portfolio,
        {"decision": "BUY"},
    )

    assert result.action == "APPROVE"
    assert result.approved is True
    assert result.score == 86.0
    assert result.nick_decision == "BUY"


def test_portfolio_decision_guard_rejects_blocked_portfolio():
    portfolio = {
        "quality": {
            "score": 92.0,
            "decision": "APPROVE",
        },
        "risk_guard": {
            "approved": False,
        },
    }

    result = PortfolioDecisionGuard().decide(
        portfolio,
        {"decision": "BUY"},
    )

    assert result.action == "REJECT"
    assert result.approved is False
    assert result.nick_decision == "BUY"


def test_portfolio_decision_guard_reduces_risk_on_low_quality():
    portfolio = {
        "quality": {
            "score": 58.0,
            "decision": "REDUCE_RISK",
        },
        "risk_guard": {
            "approved": True,
        },
    }

    result = PortfolioDecisionGuard().decide(
        portfolio,
        {"decision": "BUY"},
    )

    assert result.action == "REDUCE_RISK"
    assert result.approved is False


def test_portfolio_decision_guard_holds_cash_when_empty():
    portfolio = {
        "quality": {
            "score": 0.0,
            "decision": "HOLD_CASH",
        },
        "risk_guard": {
            "approved": True,
        },
    }

    result = PortfolioDecisionGuard().decide(
        portfolio,
        {"decision": "HOLD"},
    )

    assert result.action == "HOLD_CASH"
    assert result.approved is True


def test_portfolio_decision_guard_reviews_mid_quality_portfolio():
    portfolio = {
        "quality": {
            "score": 72.0,
            "decision": "REVIEW",
        },
        "risk_guard": {
            "approved": True,
        },
    }

    result = PortfolioDecisionGuard().decide(
        portfolio,
        {"decision": "BUY"},
    )

    assert result.action == "REVIEW"
    assert result.approved is False

from types import SimpleNamespace

from ai.research.investment.engine import InvestmentDecisionEngine


def _engine_with_scores(risk_score):
    engine = InvestmentDecisionEngine()

    engine.screening = SimpleNamespace(
        evaluate=lambda *a, **k: SimpleNamespace(
            score=80.0,
            passed=True,
            warnings=[],
        )
    )

    engine.quality = SimpleNamespace(
        calculate=lambda *a, **k: SimpleNamespace(
            score=80.0,
            completeness=100.0,
            confidence=90.0,
            warnings=[],
        )
    )

    engine.valuation = SimpleNamespace(
        calculate=lambda *a, **k: SimpleNamespace(
            score=80.0,
            pe=15.0,
            ev_ebitda=12.0,
            price_to_fcf=15.0,
            fcf_yield=0.0667,
            earnings_yield=0.05,
            margin_of_safety=0.25,
            warnings=[],
        )
    )

    engine.risk = SimpleNamespace(
        calculate=lambda *a, **k: SimpleNamespace(
            score=risk_score,
            financial_risk=20.0,
            valuation_risk=20.0,
            warnings=[],
        )
    )

    return engine


def test_higher_risk_lowers_final_score():
    metrics = {
        "revenue": 100.0,
        "net_income": 20.0,
        "free_cash_flow": 15.0,
    }

    low_risk = _engine_with_scores(20.0).analyze(metrics)
    high_risk = _engine_with_scores(80.0).analyze(metrics)

    assert low_risk["final_score"] > high_risk["final_score"]

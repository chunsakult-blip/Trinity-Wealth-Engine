from ai.research.investment.engine import (
    InvestmentDecisionEngine,
)


def test_mega_f():

    metrics = {
        "revenue": 1000.0,
        "net_income": 150.0,
        "gross_profit": 500.0,
        "operating_income": 200.0,
        "operating_cash_flow": 180.0,
        "free_cash_flow": 130.0,

        "assets": 3000.0,
        "equity": 1500.0,
        "cash": 500.0,
        "debt": 700.0,

        "roe": 0.10,
        "roic": 0.11,

        "gross_margin": 0.50,
        "operating_margin": 0.20,
        "net_margin": 0.15,

        "revenue_growth": 0.10,
        "net_income_growth": 0.12,
        "fcf_growth": 0.08,

        "net_debt": 200.0,
        "interest_coverage": 8.0,
    }

    financial_quality = {
        "score": 95.0,
        "completeness": 100.0,
        "freshness": 100.0,
        "consistency": 100.0,
        "confidence": "HIGH",
    }

    engine = InvestmentDecisionEngine()

    result = engine.evaluate(
        metrics,
        financial_quality=financial_quality,
        market_cap=3000.0,
        enterprise_value=3200.0,
    )

    assert result["status"] == "success"
    assert result["stage"] == "investment_decision"

    assert "screening" in result
    assert "quality" in result
    assert "valuation" in result
    assert "risk" in result

    assert result["screening"]["score"] >= 0
    assert result["quality"]["score"] >= 0
    assert result["valuation"]["score"] >= 0
    assert result["risk"]["score"] >= 0

    assert result["atlas_score"] >= 0
    assert result["atlas_score"] <= 100

    assert result["decision"] in {
        "PASS",
        "WATCH",
        "REJECT",
    }

    # Deterministic valuation checks.
    assert result["valuation"]["pe"] == 20.0

    assert (
        result["valuation"]["price_to_fcf"]
        == 3000.0 / 130.0
    )

    assert (
        result["valuation"]["fcf_yield"]
        == 130.0 / 3000.0
    )

    print("Screening: PASS")
    print("Quality: PASS")
    print("Valuation: PASS")
    print("Risk: PASS")
    print("ATLAS SCORE:", result["atlas_score"])
    print("DECISION:", result["decision"])


if __name__ == "__main__":
    test_mega_f()

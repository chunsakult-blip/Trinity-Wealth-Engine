from types import SimpleNamespace

from ai.agent_result import AgentResult
from ai.integration.intelligence_pipeline import IntelligencePipeline
from ai.nick.nick import Nick
from ai.research.investment.investment_bridge import InvestmentBridge


def test_pipeline_portfolio_reaches_nick(monkeypatch):
    captured = {}

    pipeline = IntelligencePipeline(
        investment_bridge=InvestmentBridge(),
    )

    # ---------------------------------------------------------
    # Keep this test deterministic and fast.
    # Only the portfolio integration boundary is under test.
    # ---------------------------------------------------------

    monkeypatch.setattr(
        pipeline.research,
        "execute",
        lambda request, **kwargs: AgentResult(
            agent="test-research",
            status="success",
            summary="research complete",
            data={
                "investable_universe": {
                    "records": [
                        {
                            "ticker": "AAPL",
                            "name": "Apple",
                            "cik": 320193,
                        }
                    ]
                }
            },
        ),
    )

    monkeypatch.setattr(
        pipeline,
        "_resolve_company",
        lambda research_result, request: {
            "ticker": "AAPL",
            "company_name": "Apple",
            "cik": 320193,
        },
    )

    monkeypatch.setattr(
        pipeline.financial,
        "analyze_company",
        lambda *args, **kwargs: {
            "status": "success",
            "ticker": "AAPL",
            "company_name": "Apple",
            "metrics": {
                "revenue": 100.0,
            },
            "quality": {
                "score": 80.0,
            },
        },
    )

    monkeypatch.setattr(
        pipeline.market_bridge,
        "enrich",
        lambda *, ticker, metrics: {
            "metrics": dict(metrics),
        },
    )

    monkeypatch.setattr(
        pipeline.investment,
        "analyze",
        lambda *args, **kwargs: {
            "status": "success",
            "stage": "investment_decision",
            "ticker": kwargs.get("ticker"),
            "company_name": kwargs.get("company_name"),
            "screening": {},
            "quality": {},
            "valuation": {},
            "risk": {"score": 20.0},
            "final_score": 85.0,
            "atlas_score": 85.0,
            "decision": "PASS",
        },
    )

    def fake_collect(*, trinity, research):
        return SimpleNamespace(
            to_dict=lambda: {"status": "success"}
        )

    monkeypatch.setattr(
        pipeline.evidence,
        "collect",
        fake_collect,
    )

    monkeypatch.setattr(
        pipeline.verifier,
        "verify",
        lambda **kwargs: SimpleNamespace(
            to_dict=lambda: {"status": "success"}
        ),
    )

    monkeypatch.setattr(
        pipeline.challenger,
        "challenge",
        lambda **kwargs: SimpleNamespace(
            to_dict=lambda: {"status": "success"}
        ),
    )

    monkeypatch.setattr(
        pipeline.reflection,
        "reflect",
        lambda **kwargs: SimpleNamespace(
            to_dict=lambda: {"status": "success"}
        ),
    )

    def fake_nick(package):
        captured["package"] = package

        return {
            "agent": "Nick",
            "role": "Chief Investment Officer",
            "status": "ready",
            "decision": "BUY",
            "investment_package": package,
        }

    monkeypatch.setattr(
        pipeline.nick,
        "evaluate",
        fake_nick,
    )

    portfolio_candidates = [
        {
            "ticker": "AAPL",
            "investment_final_score": 90.0,
            "investment_risk": {"score": 10.0},
        },
        {
            "ticker": "MSFT",
            "investment_final_score": 85.0,
            "investment_risk": {"score": 15.0},
        },
        {
            "ticker": "NVDA",
            "investment_final_score": 80.0,
            "investment_risk": {"score": 25.0},
        },
    ]

    result = pipeline.run(
        query="Build portfolio",
        tickers=[],
        trinity_output={
            "status": "success",
            "ticker": "AAPL",
            "market": "US",
        },
        portfolio_candidates=portfolio_candidates,
    )

    package = captured["package"]

    assert result["status"] == "ready"
    assert result["nick"]["status"] == "ready"

    assert "portfolio" in package

    portfolio = package["portfolio"]

    assert portfolio["status"] == "success"
    assert portfolio["candidate_count"] == 3
    assert portfolio["positions"]

    assert portfolio["total_invested"] <= 80.0
    assert portfolio["cash_weight"] >= 20.0

    assert {
        position["ticker"]
        for position in portfolio["positions"]
    } == {"AAPL", "MSFT", "NVDA"}

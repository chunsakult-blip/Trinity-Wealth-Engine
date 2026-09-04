from types import SimpleNamespace

from ai.agent_result import AgentResult
from ai.integration.intelligence_pipeline import IntelligencePipeline


def _build_pipeline(monkeypatch):
    pipeline = IntelligencePipeline()

    monkeypatch.setattr(
        pipeline.research,
        "execute",
        lambda request, **kwargs: AgentResult(
            agent="test-research",
            status="success",
            summary="research complete",
            data={"investable_universe": {"records": []}},
        ),
    )

    monkeypatch.setattr(
        pipeline.evidence,
        "collect",
        lambda **kwargs: SimpleNamespace(
            to_dict=lambda: {"status": "success"}
        ),
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

    return pipeline


def test_pipeline_includes_monitoring_without_exposing_holdings_to_nick(
    monkeypatch,
):
    pipeline = _build_pipeline(monkeypatch)

    captured = {}

    monkeypatch.setattr(
        pipeline.nick,
        "evaluate",
        lambda package: (
            captured.update({"package": package})
            or {
                "agent": "Nick",
                "status": "ready",
                "decision": "BUY",
            }
        ),
    )

    result = pipeline.run(
        query="Build portfolio",
        tickers=[],
        trinity_output={
            "status": "success",
            "ticker": "AAPL",
            "market": "US",
        },
        portfolio_candidates=[
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
        ],
        current_portfolio={
            "positions": [
                {"ticker": "AAPL", "allocation": 10.0},
                {"ticker": "MSFT", "allocation": 30.0},
                {"ticker": "TSLA", "allocation": 10.0},
            ],
            "cash_weight": 50.0,
        },
    )

    package = captured["package"]
    portfolio = package["portfolio"]

    assert result["status"] == "ready"
    assert portfolio["monitoring"]["status"] == "attention"
    assert "current_portfolio" not in package

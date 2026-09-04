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


def test_pipeline_builds_decision_and_rebalance_plan(monkeypatch):
    pipeline = _build_pipeline(monkeypatch)

    captured = {}

    def fake_nick(package):
        captured["package"] = package
        return {
            "agent": "Nick",
            "status": "ready",
            "decision": "BUY",
        }

    monkeypatch.setattr(
        pipeline.nick,
        "evaluate",
        fake_nick,
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
                {
                    "ticker": "AAPL",
                    "allocation": 10.0,
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
        },
    )

    package = captured["package"]
    portfolio = package["portfolio"]

    assert result["status"] == "ready"

    assert portfolio["risk_guard"]["approved"] is True
    assert portfolio["quality"]["score"] >= 80.0

    assert portfolio["decision"]["action"] == "APPROVE"
    assert portfolio["decision"]["nick_decision"] == "BUY"

    assert portfolio["rebalance"]["status"] == "rebalance_required"

    actions = {
        action["ticker"]: action
        for action in portfolio["rebalance"]["actions"]
    }

    assert actions["AAPL"]["action"] == "BUY"
    assert actions["MSFT"]["action"] == "SELL"
    assert actions["NVDA"]["action"] == "BUY"
    assert actions["TSLA"]["action"] == "SELL"

    assert "current_portfolio" not in package

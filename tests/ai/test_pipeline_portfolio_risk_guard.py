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


def test_pipeline_portfolio_guard_approves_safe_portfolio(monkeypatch):
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
        ],
    )

    portfolio = captured["package"]["portfolio"]

    assert result["nick"]["status"] == "ready"
    assert portfolio["status"] == "approved"
    assert portfolio["risk_guard"]["approved"] is True
    assert portfolio["cash_weight"] >= 20.0


def test_pipeline_portfolio_guard_blocks_unsafe_portfolio(monkeypatch):
    pipeline = _build_pipeline(monkeypatch)

    captured = {}

    def fake_nick(package):
        captured["package"] = package
        return {
            "agent": "Nick",
            "status": "ready",
            "decision": "HOLD",
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
                "ticker": "RISKY1",
                "investment_final_score": 95.0,
                "investment_risk": {"score": 90.0},
            },
            {
                "ticker": "RISKY2",
                "investment_final_score": 90.0,
                "investment_risk": {"score": 90.0},
            },
            {
                "ticker": "RISKY3",
                "investment_final_score": 85.0,
                "investment_risk": {"score": 90.0},
            },
        ],
    )

    portfolio = captured["package"]["portfolio"]

    assert result["nick"]["status"] == "ready"
    assert portfolio["status"] == "blocked"
    assert portfolio["risk_guard"]["approved"] is False
    assert portfolio["risk_guard"]["risk_exposure"] > 45.0
    assert portfolio["risk_guard"]["checks"]["risk_exposure"] is False

import pytest
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[2]
env_file = project_root / ".env"

load_dotenv(
    dotenv_path=env_file,
    override=False,
)

from ai.agent_result import AgentResult
from ai.integration import IntelligencePipeline
from ai.nick.nick import Nick
from ai.orchestration.research_orchestrator import ResearchOrchestrator
from ai.research.request import ResearchRequest


def test_agent_result_contract():
    result = AgentResult(
        agent="test",
        status="success",
        summary="ok",
        confidence=0.8,
    )

    assert result.success()
    assert not result.failed()
    assert result.to_dict()["agent"] == "test"


def test_research_request_normalization():
    request = ResearchRequest(
        query="  Analyze NVDA  ",
        tickers=["nvda", "NVDA", " msft "],
    )

    assert request.query == "Analyze NVDA"
    assert request.tickers == ["NVDA", "MSFT"]


def test_research_orchestrator_worker():
    def worker(request):
        return AgentResult(
            agent="US Stock Scout",
            status="success",
            summary="research complete",
            data={"tickers": request.tickers},
            evidence=[
                {"source": "test", "claim": "NVDA is relevant"}
            ],
        )

    orchestrator = ResearchOrchestrator([worker])

    result = orchestrator.execute(
        ResearchRequest(
            query="Analyze NVDA",
            tickers=["NVDA"],
        )
    )

    assert result.success()
    assert result.data["successful_workers"] == 1
    assert len(result.evidence) == 1


@pytest.mark.real_llm
def test_full_intelligence_pipeline_reaches_nick():
    pipeline = IntelligencePipeline()

    result = pipeline.run(
        query="Analyze NVIDIA investment thesis",
        tickers=["nvda"],
        trinity_output={
            "ticker": "NVDA",
            "market": "US",
            "company_name": "NVIDIA",
            "status": "success",
            "base_case_summary": "AI infrastructure leader",
            "confidence": 0.85,
            "evidence": [
                {
                    "source": "Trinity",
                    "claim": "AI infrastructure leader",
                }
            ],
        },
    )

    assert result["pipeline"] == "ATLAS Intelligence Pipeline"
    assert result["request"]["tickers"] == ["NVDA"]

    assert result["evidence"]["status"] == "success"
    assert result["verification"]["status"] == "success"
    assert result["challenge"]["status"] == "success"
    assert result["reflection"]["status"] == "success"

    assert result["nick"]["status"] == "ready"
    assert result["nick"]["decision"] is not None
    assert result["nick"]["decision"] != "PENDING_LLM_DECISION"


def test_nick_blocks_when_financial_intelligence_fails(monkeypatch):
    nick = Nick()

    called = False

    def forbidden_llm(_package):
        nonlocal called
        called = True
        raise AssertionError("Nick LLM must not run after financial failure.")

    monkeypatch.setattr(nick, "_invoke_llm", forbidden_llm)

    package = {
        "research": {"status": "success"},
        "financial": {
            "status": "failure",
            "stage": "financial_intelligence",
        },
        "investment": {
            "status": "not_run",
            "stage": "investment_decision",
        },
        "verification": {"status": "success"},
        "challenge": {"status": "success"},
        "reflection": {"status": "success"},
    }

    result = nick.evaluate(package)

    assert result["status"] == "incomplete"
    assert result["decision"] is None
    assert called is False
    assert any(
        "Financial stage failed" in warning
        for warning in result["warnings"]
    )


def test_pipeline_preserves_trinity_output():

    pipeline = IntelligencePipeline()

    source = {
        "ticker": "MSFT",
        "market": "US",
        "company_name": "Microsoft",
        "status": "success",
        "base_case_summary": "Cloud and AI",
    }

    result = pipeline.run(
        query="Analyze Microsoft",
        tickers=["MSFT"],
        trinity_output=source,
    )

    assert (
        result["trinity"]["data"]["trinity_output"]
        == source
    )

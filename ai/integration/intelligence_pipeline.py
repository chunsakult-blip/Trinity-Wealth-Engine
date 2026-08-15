"""
Trinity v2 Intelligence Pipeline.

Execution chain:

Trinity
  ↓
Adapter
  ↓
Research
  ↓
Evidence
  ↓
Verification
  ↓
Challenge
  ↓
Reflection
  ↓
Nick
"""

from __future__ import annotations

from typing import Any

from ai.agent_result import AgentResult
from ai.challenge.challenge_agent import (
    ChallengeAgent,
    DEFAULT_CHALLENGE_AGENT,
)
from ai.evidence.evidence_collector import (
    EvidenceCollector,
    DEFAULT_EVIDENCE_COLLECTOR,
)
from ai.integration.trinity_adapter import TrinityAdapter
from ai.nick.nnick import Nick
from ai.orchestration.research_orchestrator import ResearchOrchestrator
from ai.reflection.reflection_agent import (
    ReflectionAgent,
    DEFAULT_REFLECTION_AGENT,
)
from ai.research.request import ResearchRequest
from ai.verification.fact_verifier import (
    FactVerifier,
    DEFAULT_FACT_VERIFIER,
)


class IntelligencePipeline:

    name = "Trinity Intelligence Pipeline"

    def __init__(
        self,
        *,
        adapter: TrinityAdapter | None = None,
        research: ResearchOrchestrator | None = None,
        evidence: EvidenceCollector | None = None,
        verifier: FactVerifier | None = None,
        challenger: ChallengeAgent | None = None,
        reflection: ReflectionAgent | None = None,
        nick: Nick | None = None,
    ) -> None:

        self.adapter = adapter or TrinityAdapter()
        self.research = research or ResearchOrchestrator()
        self.evidence = evidence or DEFAULT_EVIDENCE_COLLECTOR
        self.verifier = verifier or DEFAULT_FACT_VERIFIER
        self.challenger = challenger or DEFAULT_CHALLENGE_AGENT
        self.reflection = reflection or DEFAULT_REFLECTION_AGENT
        self.nick = nick or Nick()

    def build_request(
        self,
        query: str,
        tickers: list[str] | None = None,
        research_type: str = "company",
        depth: str = "standard",
    ) -> ResearchRequest:

        return self.adapter.research_request(
            query=query,
            tickers=tickers,
            research_type=research_type,
            depth=depth,
        )

    def run(
        self,
        *,
        query: str,
        tickers: list[str] | None = None,
        trinity_output: Any = None,
        research_type: str = "company",
        depth: str = "standard",
    ) -> dict[str, Any]:

        request = self.build_request(
            query=query,
            tickers=tickers,
            research_type=research_type,
            depth=depth,
        )

        trinity_result = self.adapter.adapt(
            trinity_output if trinity_output is not None else {},
            query=request.query,
            tickers=request.tickers,
        )

        research_result = self.research.execute(request)

        evidence_result = self.evidence.collect(
            trinity=trinity_result,
            research=research_result,
        )

        verification_result = self.verifier.verify(
            research=research_result,
            evidence=evidence_result,
        )

        challenge_result = self.challenger.challenge(
            research=research_result,
            verification=verification_result,
        )

        reflection_result = self.reflection.reflect(
            research=research_result,
            verification=verification_result,
            challenge=challenge_result,
        )

        investment_package = {
            "request": request.to_dict(),
            "trinity": trinity_result.to_dict(),
            "research": research_result.to_dict(),
            "evidence": evidence_result.to_dict(),
            "verification": verification_result.to_dict(),
            "challenge": challenge_result.to_dict(),
            "reflection": reflection_result.to_dict(),
        }

        nick_result = self.nick.evaluate(
            investment_package
        )

        return {
            "pipeline": self.name,
            "status": (
                "ready"
                if nick_result["status"] == "ready"
                else "incomplete"
            ),
            "request": request.to_dict(),
            "trinity": trinity_result.to_dict(),
            "research": research_result.to_dict(),
            "evidence": evidence_result.to_dict(),
            "verification": verification_result.to_dict(),
            "challenge": challenge_result.to_dict(),
            "reflection": reflection_result.to_dict(),
            "nick": nick_result,
        }


DEFAULT_INTELLIGENCE_PIPELINE = IntelligencePipeline()

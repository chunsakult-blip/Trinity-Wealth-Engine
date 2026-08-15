"""
Reflection Agent.

Reviews the research/verification/challenge state before
final investment reasoning.
"""

from __future__ import annotations

from ai.agent_result import AgentResult


class ReflectionAgent:

    name = "Reflection Agent"

    def reflect(
        self,
        *,
        research: AgentResult,
        verification: AgentResult,
        challenge: AgentResult,
    ) -> AgentResult:

        observations: list[str] = []

        if research.warnings:
            observations.append(
                "Research contains warnings."
            )

        if verification.data.get("unverified_count", 0):
            observations.append(
                "Some evidence remains unverified."
            )

        if challenge.data.get("challenge_count", 0):
            observations.append(
                "Challenge findings exist and must be "
                "considered by Nick."
            )

        if not observations:
            observations.append(
                "No structural issues detected."
            )

        return AgentResult(
            agent=self.name,
            status="success",
            summary="Reflection stage completed.",
            data={
                "observations": observations,
                "reflection_ready": True,
            },
            warnings=[],
        )


DEFAULT_REFLECTION_AGENT = ReflectionAgent()

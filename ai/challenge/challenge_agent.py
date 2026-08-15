"""
Challenge Agent.

Attempts to identify weaknesses, missing evidence and
unsupported assumptions in the investment package.
"""

from __future__ import annotations

from typing import Any

from ai.agent_result import AgentResult


class ChallengeAgent:

    name = "Challenge Agent"

    def challenge(
        self,
        *,
        research: AgentResult,
        verification: AgentResult,
    ) -> AgentResult:

        findings: list[dict[str, Any]] = []
        warnings: list[str] = []

        if research.failed():
            findings.append(
                {
                    "type": "research_failure",
                    "severity": "high",
                    "message": research.summary,
                }
            )

        if verification.data.get("unverified_count", 0) > 0:
            count = verification.data["unverified_count"]

            findings.append(
                {
                    "type": "unverified_evidence",
                    "severity": "medium",
                    "message": (
                        f"{count} evidence item(s) "
                        "remain unverified."
                    ),
                }
            )

        if not findings:
            findings.append(
                {
                    "type": "no_structural_challenge",
                    "severity": "info",
                    "message": (
                        "No structural challenge was generated "
                        "by the deterministic layer."
                    ),
                }
            )

        return AgentResult(
            agent=self.name,
            status="success",
            summary=(
                f"Generated {len(findings)} challenge finding(s)."
            ),
            data={
                "findings": findings,
                "challenge_count": len(findings),
            },
            warnings=warnings,
        )


DEFAULT_CHALLENGE_AGENT = ChallengeAgent()

"""
Fact Verification layer.

Deterministic architecture boundary for future LLM-assisted
fact verification.
"""

from __future__ import annotations

from typing import Any

from ai.agent_result import AgentResult


class FactVerifier:

    name = "Fact Verifier"

    def verify(
        self,
        *,
        research: AgentResult,
        evidence: AgentResult,
    ) -> AgentResult:

        evidence_items = list(
            evidence.data.get("evidence", [])
        )

        checks: list[dict[str, Any]] = []

        for item in evidence_items:
            checks.append(
                {
                    "evidence_id": item.get("evidence_id"),
                    "status": "unverified",
                    "reason": (
                        "Deterministic verification boundary; "
                        "external source validation is required."
                    ),
                }
            )

        warnings = list(research.warnings)

        if not evidence_items:
            warnings.append(
                "Verification has no evidence items to evaluate."
            )

        return AgentResult(
            agent=self.name,
            status="success",
            summary=(
                f"Prepared {len(checks)} evidence item(s) "
                "for verification."
            ),
            data={
                "verification_status": (
                    "pending_external_validation"
                ),
                "checks": checks,
                "verified_count": 0,
                "unverified_count": len(checks),
            },
            evidence=evidence_items,
            warnings=list(dict.fromkeys(warnings)),
        )


DEFAULT_FACT_VERIFIER = FactVerifier()

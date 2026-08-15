"""
Evidence Collector.

Normalizes evidence coming from Trinity and research workers.
"""

from __future__ import annotations

from typing import Any

from ai.agent_result import AgentResult


class EvidenceCollector:

    name = "Evidence Collector"

    def collect(
        self,
        *,
        trinity: AgentResult,
        research: AgentResult,
    ) -> AgentResult:

        evidence: list[dict[str, Any]] = []

        evidence.extend(trinity.evidence)
        evidence.extend(research.evidence)

        normalized: list[dict[str, Any]] = []

        for index, item in enumerate(evidence, start=1):
            if isinstance(item, dict):
                record = dict(item)
            else:
                record = {"source": str(item)}

            record.setdefault("evidence_id", f"E{index:04d}")
            normalized.append(record)

        warnings: list[str] = []

        if not normalized:
            warnings.append(
                "No structured evidence was supplied."
            )

        status = "success"

        return AgentResult(
            agent=self.name,
            status=status,
            summary=(
                f"Collected {len(normalized)} evidence item(s)."
            ),
            data={
                "evidence_count": len(normalized),
                "evidence": normalized,
            },
            evidence=normalized,
            warnings=warnings,
        )


DEFAULT_EVIDENCE_COLLECTOR = EvidenceCollector()

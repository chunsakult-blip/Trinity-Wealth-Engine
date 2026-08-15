"""
Shared contract for Trinity v2 AI agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    agent: str
    status: str
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float | None = None

    def success(self) -> bool:
        return self.status == "success"

    def failed(self) -> bool:
        return self.status in {"failure", "error"}

    def incomplete(self) -> bool:
        return self.status == "incomplete"

    def with_data(self, **updates: Any) -> "AgentResult":
        merged = dict(self.data)
        merged.update(updates)

        return AgentResult(
            agent=self.agent,
            status=self.status,
            summary=self.summary,
            data=merged,
            evidence=list(self.evidence),
            warnings=list(self.warnings),
            confidence=self.confidence,
        )

    def add_warning(self, warning: str) -> "AgentResult":
        warnings = list(self.warnings)

        if warning and warning not in warnings:
            warnings.append(warning)

        return AgentResult(
            agent=self.agent,
            status=self.status,
            summary=self.summary,
            data=dict(self.data),
            evidence=list(self.evidence),
            warnings=warnings,
            confidence=self.confidence,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "status": self.status,
            "summary": self.summary,
            "data": dict(self.data),
            "evidence": list(self.evidence),
            "warnings": list(self.warnings),
            "confidence": self.confidence,
        }

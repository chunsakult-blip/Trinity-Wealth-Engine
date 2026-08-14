"""
Shared contract for Trinity AI agents.

Agents communicate through structured results instead of passing
arbitrary strings directly between one another.
"""

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

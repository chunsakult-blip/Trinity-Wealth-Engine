from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PortfolioDecision:
    action: str
    approved: bool
    score: float
    nick_decision: str | None
    reasons: list[str]


class PortfolioDecisionGuard:
    """
    Deterministic final boundary for portfolio decisions.

    No LLM call.
    No external I/O.
    O(1) decision after upstream portfolio scoring.
    """

    def decide(
        self,
        portfolio: dict[str, Any],
        nick_result: dict[str, Any] | None = None,
    ) -> PortfolioDecision:
        quality = portfolio.get("quality") or {}
        risk_guard = portfolio.get("risk_guard") or {}

        score = float(quality.get("score", 0.0) or 0.0)
        quality_decision = str(
            quality.get("decision", "")
        ).upper()

        nick_decision_value = (
            nick_result.get("decision")
            if isinstance(nick_result, dict)
            else None
        )
        nick_decision = (
            str(nick_decision_value).upper()
            if nick_decision_value is not None
            else None
        )

        reasons: list[str] = []

        if not bool(risk_guard.get("approved", True)):
            reasons.append("Portfolio risk guard is blocked.")
            return PortfolioDecision(
                action="REJECT",
                approved=False,
                score=score,
                nick_decision=nick_decision,
                reasons=reasons,
            )

        if quality_decision == "HOLD_CASH":
            reasons.append("Portfolio has no allocated positions.")
            return PortfolioDecision(
                action="HOLD_CASH",
                approved=True,
                score=score,
                nick_decision=nick_decision,
                reasons=reasons,
            )

        if score < 65.0:
            reasons.append("Portfolio quality is below approval threshold.")
            return PortfolioDecision(
                action="REDUCE_RISK",
                approved=False,
                score=score,
                nick_decision=nick_decision,
                reasons=reasons,
            )

        if score < 80.0:
            reasons.append("Portfolio quality requires review.")
            return PortfolioDecision(
                action="REVIEW",
                approved=False,
                score=score,
                nick_decision=nick_decision,
                reasons=reasons,
            )

        reasons.append("Portfolio quality and risk guard passed.")
        return PortfolioDecision(
            action="APPROVE",
            approved=True,
            score=score,
            nick_decision=nick_decision,
            reasons=reasons,
        )

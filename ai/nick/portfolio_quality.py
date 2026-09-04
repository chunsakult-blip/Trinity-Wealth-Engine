from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class PortfolioQuality:
    score: float
    decision: str
    investment_quality: float
    risk_quality: float
    concentration_quality: float
    cash_quality: float
    reasons: list[str]


class PortfolioQualityEngine:
    """
    Deterministic portfolio quality scoring.

    Performance:
        O(n) over portfolio positions
        No LLM call
        No external I/O
    """

    def evaluate(
        self,
        portfolio: dict[str, Any],
        *,
        min_cash: float = 20.0,
    ) -> PortfolioQuality:
        positions = list(portfolio.get("positions") or [])
        cash_weight = float(portfolio.get("cash_weight", 0.0) or 0.0)
        risk_exposure = float(
            portfolio.get("risk_guard", {}).get("risk_exposure", 0.0) or 0.0
        )

        total_invested = sum(
            max(float(position.get("allocation", 0.0) or 0.0), 0.0)
            for position in positions
        )

        if total_invested > 0.0:
            weighted_score = sum(
                max(float(position.get("score", 0.0) or 0.0), 0.0)
                * max(float(position.get("allocation", 0.0) or 0.0), 0.0)
                for position in positions
            ) / total_invested
        else:
            weighted_score = 0.0

        investment_quality = _clamp(weighted_score)

        weighted_risk = sum(
            max(float(position.get("risk_score", 0.0) or 0.0), 0.0)
            * max(float(position.get("allocation", 0.0) or 0.0), 0.0)
            for position in positions
        )

        if total_invested > 0.0:
            weighted_risk /= total_invested

        risk_quality = _clamp(100.0 - max(weighted_risk, risk_exposure))

        max_position = max(
            (
                float(position.get("allocation", 0.0) or 0.0)
                for position in positions
            ),
            default=0.0,
        )

        concentration_quality = _clamp(100.0 - (max_position * 2.0))

        if cash_weight >= min_cash:
            cash_quality = 100.0
        elif min_cash > 0.0:
            cash_quality = _clamp((cash_weight / min_cash) * 100.0)
        else:
            cash_quality = 100.0

        score = round(
            (
                investment_quality * 0.45
                + risk_quality * 0.30
                + concentration_quality * 0.15
                + cash_quality * 0.10
            ),
            2,
        )

        reasons: list[str] = []

        if investment_quality < 65.0:
            reasons.append("Investment quality is weak.")

        if risk_quality < 60.0:
            reasons.append("Portfolio risk is elevated.")

        if concentration_quality < 60.0:
            reasons.append("Portfolio concentration is high.")

        if cash_quality < 100.0:
            reasons.append("Cash buffer is below target.")

        guard_approved = bool(
            portfolio.get("risk_guard", {}).get("approved", True)
        )

        if not positions or total_invested <= 0.0:
            return PortfolioQuality(
                score=0.0,
                decision="HOLD_CASH",
                investment_quality=0.0,
                risk_quality=100.0,
                concentration_quality=100.0,
                cash_quality=round(cash_quality, 2),
                reasons=["No portfolio positions are allocated."],
            )

        if not guard_approved:
            decision = "REJECT"
            reasons.insert(0, "Portfolio risk guard is blocked.")
        elif score >= 80.0:
            decision = "APPROVE"
        elif score >= 65.0:
            decision = "REVIEW"
        else:
            decision = "REDUCE_RISK"

        return PortfolioQuality(
            score=score,
            decision=decision,
            investment_quality=round(investment_quality, 2),
            risk_quality=round(risk_quality, 2),
            concentration_quality=round(concentration_quality, 2),
            cash_quality=round(cash_quality, 2),
            reasons=reasons,
        )

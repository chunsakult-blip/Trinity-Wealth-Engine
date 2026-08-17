"""
Deterministic investment risk scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RiskResult:
    score: float
    level: str
    leverage_risk: float
    profitability_risk: float
    cash_flow_risk: float
    valuation_risk: float
    data_risk: float
    warnings: list[str]


class RiskEngine:

    def calculate(
        self,
        metrics: dict[str, Any],
        *,
        valuation_score: float = 0.0,
        financial_quality: dict[str, Any] | None = None,
    ) -> RiskResult:

        financial_quality = financial_quality or {}

        warnings: list[str] = []

        debt = metrics.get("debt")
        cash = metrics.get("cash")
        net_income = metrics.get("net_income")
        fcf = metrics.get("free_cash_flow")

        # ------------------------------------------------------------
        # LEVERAGE
        # ------------------------------------------------------------

        leverage_risk = 50.0

        if debt is not None and cash is not None:

            if debt <= cash:
                leverage_risk = 10.0
            elif debt <= cash * 2:
                leverage_risk = 25.0
            elif debt <= cash * 4:
                leverage_risk = 50.0
            else:
                leverage_risk = 85.0
                warnings.append(
                    "Debt materially exceeds cash."
                )

        # ------------------------------------------------------------
        # PROFITABILITY
        # ------------------------------------------------------------

        profitability_risk = 50.0

        if net_income is not None:

            profitability_risk = (
                15.0
                if net_income > 0
                else 90.0
            )

        # ------------------------------------------------------------
        # CASH FLOW
        # ------------------------------------------------------------

        cash_flow_risk = 50.0

        if fcf is not None:

            cash_flow_risk = (
                15.0
                if fcf > 0
                else 90.0
            )

        # ------------------------------------------------------------
        # VALUATION
        # ------------------------------------------------------------

        valuation_risk = max(
            0.0,
            min(
                100.0,
                100.0 - valuation_score,
            ),
        )

        if valuation_score < 40:
            warnings.append(
                "Valuation risk is elevated."
            )

        # ------------------------------------------------------------
        # DATA
        # ------------------------------------------------------------

        quality_score = float(
            financial_quality.get(
                "score",
                0.0,
            )
        )

        data_risk = max(
            0.0,
            min(
                100.0,
                100.0 - quality_score,
            ),
        )

        if data_risk > 40:
            warnings.append(
                "Financial data quality risk is elevated."
            )

        # ------------------------------------------------------------
        # TOTAL
        # ------------------------------------------------------------

        score = (
            leverage_risk * 0.25
            + profitability_risk * 0.20
            + cash_flow_risk * 0.20
            + valuation_risk * 0.20
            + data_risk * 0.15
        )

        if score < 25:
            level = "LOW"
        elif score < 50:
            level = "MEDIUM"
        elif score < 75:
            level = "HIGH"
        else:
            level = "SEVERE"

        return RiskResult(
            score=round(score, 2),
            level=level,
            leverage_risk=round(
                leverage_risk,
                2,
            ),
            profitability_risk=round(
                profitability_risk,
                2,
            ),
            cash_flow_risk=round(
                cash_flow_risk,
                2,
            ),
            valuation_risk=round(
                valuation_risk,
                2,
            ),
            data_risk=round(
                data_risk,
                2,
            ),
            warnings=warnings,
        )

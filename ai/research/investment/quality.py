"""
Deterministic financial quality scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class QualityScore:
    score: float
    profitability: float
    growth: float
    balance_sheet: float
    cash_flow: float
    confidence: float
    warnings: list[str]


class InvestmentQualityEngine:

    def calculate(
        self,
        metrics: dict[str, Any],
        financial_quality: dict[str, Any] | None = None,
    ) -> QualityScore:

        financial_quality = financial_quality or {}

        warnings: list[str] = []

        def clamp(value: float) -> float:
            return max(0.0, min(100.0, value))

        # ------------------------------------------------------------
        # PROFITABILITY
        # ------------------------------------------------------------

        roe = metrics.get("roe")
        roic = metrics.get("roic")
        gross_margin = metrics.get("gross_margin")
        operating_margin = metrics.get("operating_margin")

        profitability_parts: list[float] = []

        if roe is not None:
            profitability_parts.append(
                clamp((roe / 0.20) * 100.0)
            )

        if roic is not None:
            profitability_parts.append(
                clamp((roic / 0.20) * 100.0)
            )

        if gross_margin is not None:
            profitability_parts.append(
                clamp((gross_margin / 0.60) * 100.0)
            )

        if operating_margin is not None:
            profitability_parts.append(
                clamp((operating_margin / 0.30) * 100.0)
            )

        profitability = (
            sum(profitability_parts)
            / len(profitability_parts)
            if profitability_parts
            else 0.0
        )

        # ------------------------------------------------------------
        # GROWTH
        # ------------------------------------------------------------

        growth_parts: list[float] = []

        for key in (
            "revenue_growth",
            "net_income_growth",
            "fcf_growth",
        ):

            value = metrics.get(key)

            if value is not None:
                growth_parts.append(
                    clamp(
                        50.0
                        + value * 250.0
                    )
                )

        growth = (
            sum(growth_parts)
            / len(growth_parts)
            if growth_parts
            else 50.0
        )

        # ------------------------------------------------------------
        # BALANCE SHEET
        # ------------------------------------------------------------

        balance_parts: list[float] = []

        debt = metrics.get("debt")
        cash = metrics.get("cash")
        net_debt = metrics.get("net_debt")
        interest_coverage = metrics.get(
            "interest_coverage"
        )

        if debt is not None and cash is not None:

            if debt <= cash:
                balance_parts.append(100.0)
            elif debt <= cash * 2:
                balance_parts.append(85.0)
            elif debt <= cash * 4:
                balance_parts.append(65.0)
            else:
                balance_parts.append(30.0)

        if net_debt is not None:

            if net_debt <= 0:
                balance_parts.append(100.0)
            elif net_debt < 1_000_000_000:
                balance_parts.append(80.0)
            else:
                balance_parts.append(60.0)

        if interest_coverage is not None:

            balance_parts.append(
                clamp(
                    interest_coverage * 10.0
                )
            )

        balance_sheet = (
            sum(balance_parts)
            / len(balance_parts)
            if balance_parts
            else 50.0
        )

        # ------------------------------------------------------------
        # CASH FLOW
        # ------------------------------------------------------------

        fcf = metrics.get("free_cash_flow")
        ocf = metrics.get("operating_cash_flow")

        cash_flow_parts: list[float] = []

        if fcf is not None:

            cash_flow_parts.append(
                100.0
                if fcf > 0
                else 0.0
            )

        if ocf is not None:

            cash_flow_parts.append(
                100.0
                if ocf > 0
                else 0.0
            )

        cash_flow = (
            sum(cash_flow_parts)
            / len(cash_flow_parts)
            if cash_flow_parts
            else 0.0
        )

        # ------------------------------------------------------------
        # DATA CONFIDENCE
        # ------------------------------------------------------------

        confidence = float(
            financial_quality.get(
                "score",
                0.0,
            )
        )

        if confidence < 60:
            warnings.append(
                "Financial data confidence is below 60."
            )

        score = (
            profitability * 0.35
            + growth * 0.20
            + balance_sheet * 0.20
            + cash_flow * 0.15
            + confidence * 0.10
        )

        return QualityScore(
            score=round(score, 2),
            profitability=round(
                profitability,
                2,
            ),
            growth=round(
                growth,
                2,
            ),
            balance_sheet=round(
                balance_sheet,
                2,
            ),
            cash_flow=round(
                cash_flow,
                2,
            ),
            confidence=round(
                confidence,
                2,
            ),
            warnings=warnings,
        )

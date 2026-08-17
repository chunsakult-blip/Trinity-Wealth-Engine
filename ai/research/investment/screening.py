"""
Deterministic investment screening layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScreeningResult:
    passed: bool
    score: float
    reasons: list[str]
    failures: list[str]


class InvestmentScreeningEngine:

    def evaluate(
        self,
        metrics: dict[str, Any],
        *,
        market_cap: float | None = None,
        price: float | None = None,
    ) -> ScreeningResult:

        checks = 0
        passed = 0

        reasons: list[str] = []
        failures: list[str] = []

        def check(
            condition: bool,
            success: str,
            failure: str,
        ) -> None:

            nonlocal checks, passed

            checks += 1

            if condition:
                passed += 1
                reasons.append(success)
            else:
                failures.append(failure)

        revenue = metrics.get("revenue")
        net_income = metrics.get("net_income")
        fcf = metrics.get("free_cash_flow")
        roe = metrics.get("roe")
        roic = metrics.get("roic")
        debt = metrics.get("debt")
        cash = metrics.get("cash")

        check(
            revenue is not None and revenue > 0,
            "Positive revenue.",
            "Revenue unavailable or non-positive.",
        )

        check(
            net_income is not None and net_income > 0,
            "Positive net income.",
            "Net income unavailable or non-positive.",
        )

        check(
            fcf is not None and fcf > 0,
            "Positive free cash flow.",
            "Free cash flow unavailable or non-positive.",
        )

        check(
            roe is not None and roe > 0.08,
            "ROE above 8%.",
            "ROE below 8% or unavailable.",
        )

        check(
            roic is not None and roic > 0.08,
            "ROIC above 8%.",
            "ROIC below 8% or unavailable.",
        )

        if debt is not None and cash is not None:
            check(
                debt <= cash * 4.0,
                "Debt level within screening tolerance.",
                "Debt materially exceeds cash.",
            )

        if market_cap is not None:
            check(
                market_cap > 0,
                "Positive market capitalization.",
                "Invalid market capitalization.",
            )

        score = (
            passed / checks * 100.0
            if checks
            else 0.0
        )

        # Hard rejection conditions.
        hard_fail = (
            revenue is not None and revenue <= 0
        ) or (
            net_income is not None and net_income <= 0
        )

        return ScreeningResult(
            passed=(
                score >= 65.0
                and not hard_fail
            ),
            score=round(score, 2),
            reasons=reasons,
            failures=failures,
        )

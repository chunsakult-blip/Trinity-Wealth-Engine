"""
Canonical deterministic financial data quality engine.

This is the ONLY authoritative financial-data quality scorer.

Contract:
    NormalizedFinancials
        -> FinancialQuality
"""

from __future__ import annotations

from .models import (
    FinancialQuality,
    NormalizedFinancials,
)


class FinancialQualityEngine:

    REQUIRED_METRICS = (
        "revenue",
        "net_income",
        "free_cash_flow",
        "gross_margin",
        "operating_margin",
        "roe",
        "roic",
    )

    def evaluate(
        self,
        financials: NormalizedFinancials,
    ) -> FinancialQuality:

        metrics = financials.metrics or {}

        available = sum(
            1
            for key in self.REQUIRED_METRICS
            if metrics.get(key) is not None
        )

        completeness = (
            available
            / len(self.REQUIRED_METRICS)
        )

        consistency = self._consistency(
            metrics
        )

        # True normalized TTM is the preferred freshness signal.
        freshness = (
            1.0
            if financials.ttm is not None
            else 0.0
        )

        score = (
            completeness * 0.50
            + consistency * 0.30
            + freshness * 0.20
        ) * 100.0

        warnings: list[str] = []

        if completeness < 0.60:
            warnings.append(
                "Financial fact completeness below 60%."
            )

        if metrics.get("free_cash_flow") is None:
            warnings.append(
                "Free cash flow unavailable."
            )

        if metrics.get("roic") is None:
            warnings.append(
                "ROIC unavailable."
            )

        if financials.ttm is None:
            warnings.append(
                "No normalized TTM financial data available."
            )

        confidence = (
            "HIGH"
            if score >= 85
            else "MEDIUM"
            if score >= 65
            else "LOW"
        )

        quality = FinancialQuality(
            score=round(score, 2),
            completeness=round(
                completeness * 100.0,
                2,
            ),
            freshness=round(
                freshness * 100.0,
                2,
            ),
            consistency=round(
                consistency * 100.0,
                2,
            ),
            confidence=confidence,
            warnings=warnings,
        )

        financials.quality = {
            "score": quality.score,
            "completeness": quality.completeness,
            "freshness": quality.freshness,
            "consistency": quality.consistency,
            "confidence": quality.confidence,
            "warnings": list(
                quality.warnings
            ),
        }

        return quality

    @staticmethod
    def _consistency(
        metrics: dict[str, float | None],
    ) -> float:

        checks = 0
        passed = 0

        revenue = metrics.get("revenue")

        if revenue is not None:
            checks += 1

            if revenue >= 0:
                passed += 1

        net_income = metrics.get(
            "net_income"
        )

        if net_income is not None:
            checks += 1

            if abs(net_income) < 1e18:
                passed += 1

        gross_margin = metrics.get(
            "gross_margin"
        )

        if gross_margin is not None:
            checks += 1

            if -2.0 <= gross_margin <= 2.0:
                passed += 1

        operating_margin = metrics.get(
            "operating_margin"
        )

        if operating_margin is not None:
            checks += 1

            if -2.0 <= operating_margin <= 2.0:
                passed += 1

        roe = metrics.get("roe")

        if roe is not None:
            checks += 1

            if -10.0 <= roe <= 10.0:
                passed += 1

        roic = metrics.get("roic")

        if roic is not None:
            checks += 1

            if -10.0 <= roic <= 10.0:
                passed += 1

        if checks == 0:
            return 0.0

        return passed / checks

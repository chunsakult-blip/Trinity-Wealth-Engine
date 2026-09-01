"""
Financial Intelligence production facade.

Pipeline:

SEC Company Facts
    -> normalization
    -> deterministic metrics
    -> quality scoring
    -> evidence
"""

from __future__ import annotations

from typing import Any

from .metrics import FinancialMetricsEngine
from .normalizer import FinancialFactNormalizer
from .quality import FinancialQualityEngine
from .sec_provider import SECCompanyFactsProvider


class FinancialIntelligenceEngine:

    def __init__(
        self,
        *,
        user_agent: str | None = None,
    ) -> None:

        self.provider = SECCompanyFactsProvider(
            user_agent=user_agent,
        )

        self.normalizer = FinancialFactNormalizer()
        self.metrics = FinancialMetricsEngine()
        self.quality = FinancialQualityEngine()

    def analyze_company(
        self,
        cik: int,
        *,
        ticker: str | None = None,
        company_name: str | None = None,
    ) -> dict[str, Any]:

        # --------------------------------------------------------
        # CANONICAL CIK TYPE CONTRACT
        #
        # GrowthUniverse candidates may carry CIK as str.
        # SECProvider requires numeric CIK because it performs
        # numeric validation and formatting.
        #
        # Normalize once at the financial-engine boundary so all
        # downstream financial components receive canonical int CIK.
        # --------------------------------------------------------

        try:
            cik = int(cik)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid CIK: {cik!r}. Expected numeric CIK."
            ) from exc

        if cik <= 0:
            raise ValueError(
                f"Invalid CIK: {cik!r}. Expected positive CIK."
            )

        payload = self.provider.fetch(cik)

        financials = self.normalizer.normalize(
            payload,
            cik=cik,
            ticker=ticker,
            company_name=company_name,
        )

        # Derived metrics.
        calculated_metrics = (
            self.metrics.calculate(
                financials
            )
        )

        # IMPORTANT:
        # Quality must evaluate the complete metric set,
        # including derived metrics.
        financials.metrics.update(
            {
                key: value
                for key, value in vars(
                    calculated_metrics
                ).items()
                if value is not None
            }
        )

        quality = self.quality.evaluate(
            financials
        )

        return {
            "status": "success",
            "market": "US",
            "stage": "financial_intelligence",

            "cik": cik,
            "ticker": ticker,
            "company_name": (
                financials.company_name
            ),

            "metrics": dict(
                financials.metrics
            ),

            "quality": {
                "score": quality.score,
                "completeness": (
                    quality.completeness
                ),
                "freshness": (
                    quality.freshness
                ),
                "consistency": (
                    quality.consistency
                ),
                "confidence": (
                    quality.confidence
                ),
                "warnings": list(
                    quality.warnings
                ),
            },

            "latest_period": (
                vars(
                    financials.latest_period
                )
                if financials.latest_period
                else None
            ),

            "prior_period": (
                vars(
                    financials.prior_period
                )
                if financials.prior_period
                else None
            ),

            "ttm": (
                vars(financials.ttm)
                if financials.ttm
                else None
            ),

            "period_count": len(
                financials.periods
            ),

            "evidence": list(
                financials.evidence
            ),
        }

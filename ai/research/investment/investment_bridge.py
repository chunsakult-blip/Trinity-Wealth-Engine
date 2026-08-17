from __future__ import annotations

from typing import Any

from ai.research.investment.engine import InvestmentDecisionEngine


class InvestmentBridge:
    """
    Converts a ranked research candidate into an
    InvestmentDecisionEngine decision.

    Architecture:

        Candidate
            -> financial_metrics extraction
            -> InvestmentDecisionEngine
            -> normalized investment decision

    This layer does not modify candidate ranking.

    candidate_score:
        discovery / research priority

    final_score:
        investment decision quality

    These are intentionally separate signals.
    """

    def __init__(
        self,
        engine: InvestmentDecisionEngine | None = None,
    ) -> None:

        self.engine = (
            engine
            if engine is not None
            else InvestmentDecisionEngine()
        )

    def evaluate(
        self,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:

        item = dict(candidate)

        ticker = (
            str(item.get("ticker") or "").strip().upper()
            or None
        )

        company_name = (
            item.get("company_name")
            or item.get("name")
        )

        metrics = self._metrics(item)

        financial_quality = self._financial_quality(item)

        market_cap = self._number(
            item.get("market_cap")
        )

        enterprise_value = self._number(
            item.get("enterprise_value")
        )

        price = self._number(
            item.get("price")
        )

        # ------------------------------------------------------------
        # INVESTMENT ENGINE
        # ------------------------------------------------------------

        result = self.engine.evaluate(
            metrics,
            financial_quality=financial_quality,
            market_cap=market_cap,
            enterprise_value=enterprise_value,
            price=price,
            ticker=ticker,
            company_name=company_name,
        )

        if not isinstance(result, dict):
            raise TypeError(
                "InvestmentDecisionEngine returned "
                "a non-dictionary result."
            )

        # ------------------------------------------------------------
        # BRIDGE CONTRACT
        # ------------------------------------------------------------

        output = {
            "investment_status": result.get(
                "status",
                "failed",
            ),

            "investment_stage": result.get(
                "stage",
                "investment_decision",
            ),

            "investment_ticker": result.get(
                "ticker",
                ticker,
            ),

            "investment_company_name": result.get(
                "company_name",
                company_name,
            ),

            "investment_screening":
                result.get("screening") or {},

            "investment_quality":
                result.get("quality") or {},

            "investment_valuation":
                result.get("valuation") or {},

            "investment_risk":
                result.get("risk") or {},

            "investment_final_score":
                self._number(
                    result.get("final_score")
                ),

            "investment_atlas_score":
                self._number(
                    result.get("atlas_score")
                ),

            "investment_decision":
                result.get("decision"),

        }

        return output

    def evaluate_and_merge(
        self,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:

        item = dict(candidate)

        result = self.evaluate(item)

        item.update(result)

        return item

    @staticmethod
    def _metrics(
        candidate: dict[str, Any],
    ) -> dict[str, Any]:

        metrics = candidate.get(
            "financial_metrics"
        )

        if isinstance(metrics, dict):
            return dict(metrics)

        # ------------------------------------------------------------
        # Fallback for candidates that already expose
        # financial fields at the top level.
        # ------------------------------------------------------------

        financial_keys = {
            "revenue",
            "gross_profit",
            "operating_income",
            "net_income",
            "assets",
            "equity",
            "cash",
            "debt",
            "operating_cash_flow",
            "capex",
            "interest_expense",
            "income_tax_expense",
            "free_cash_flow",
            "tax_rate",
            "revenue_growth",
            "net_income_growth",
            "fcf_growth",
            "gross_margin",
            "operating_margin",
            "net_margin",
            "roe",
            "roic",
            "debt_to_equity",
            "net_debt",
            "interest_coverage",
        }

        return {
            key: candidate.get(key)
            for key in financial_keys
            if key in candidate
        }

    @staticmethod
    def _financial_quality(
        candidate: dict[str, Any],
    ) -> dict[str, Any] | None:

        quality_keys = (
            "financial_quality_score",
            "financial_completeness",
            "financial_freshness",
            "financial_consistency",
            "financial_confidence",
            "financial_warnings",
        )

        quality: dict[str, Any] = {}

        if candidate.get(
            "financial_quality_score"
        ) is not None:
            quality["score"] = candidate.get(
                "financial_quality_score"
            )

        if candidate.get(
            "financial_completeness"
        ) is not None:
            quality["completeness"] = candidate.get(
                "financial_completeness"
            )

        if candidate.get(
            "financial_freshness"
        ) is not None:
            quality["freshness"] = candidate.get(
                "financial_freshness"
            )

        if candidate.get(
            "financial_consistency"
        ) is not None:
            quality["consistency"] = candidate.get(
                "financial_consistency"
            )

        if candidate.get(
            "financial_confidence"
        ) is not None:
            quality["confidence"] = candidate.get(
                "financial_confidence"
            )

        if candidate.get(
            "financial_warnings"
        ) is not None:
            quality["warnings"] = list(
                candidate.get(
                    "financial_warnings"
                ) or []
            )

        if not quality:
            return None

        return quality

    @staticmethod
    def _number(
        value: Any,
    ) -> float | None:

        if value is None:
            return None

        try:
            number = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if number != number:
            return None

        return number

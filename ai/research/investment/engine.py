from __future__ import annotations

from typing import Any

from .quality import InvestmentQualityEngine
from .risk import RiskEngine
from .screening import InvestmentScreeningEngine
from .valuation import ValuationEngine


class InvestmentDecisionEngine:

    def __init__(self) -> None:
        self.screening = InvestmentScreeningEngine()
        self.quality = InvestmentQualityEngine()
        self.valuation = ValuationEngine()
        self.risk = RiskEngine()

    @staticmethod
    def _number(
        value: Any,
    ) -> float | None:

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_metrics(
        metrics: dict[str, Any],
    ) -> dict[str, float | None]:

        # ------------------------------------------------------------
        # INPUT BOUNDARY
        #
        # Supported inputs:
        #   1. Legacy dict
        #   2. NormalizedFinancials
        #   3. NormalizedFinancials.ttm
        #
        # Canonical derived metrics such as EBITDA live inside
        # NormalizedFinancials.metrics and must be promoted into the
        # flat InvestmentDecisionEngine namespace.
        # ------------------------------------------------------------

        source = metrics

        # NormalizedFinancials
        if hasattr(metrics, "metrics"):
            nested_metrics = getattr(
                metrics,
                "metrics",
                None,
            )

            if isinstance(nested_metrics, dict):
                source = nested_metrics

        # FinancialPeriod / other dataclass-like objects
        elif hasattr(metrics, "__dataclass_fields__"):
            fields = getattr(
                metrics,
                "__dataclass_fields__",
                {},
            )

            source = {
                key: getattr(metrics, key)
                for key in fields
                if hasattr(metrics, key)
            }

        normalized: dict[str, float | None] = {}

        if isinstance(source, dict):

            for key, value in source.items():

                normalized[key] = (
                    InvestmentDecisionEngine._number(value)
                )

        aliases = {
            "free_cash_flow": (
                "fcf",
                "free_cashflow",
                "free_cash_flow_ttm",
            ),
            "net_income": (
                "net_income_ttm",
                "earnings",
                "profit",
            ),
            "operating_income": (
                "ebit",
                "operating_profit",
            ),
            "depreciation_and_amortization": (
                "da",
                "d_and_a",
                "depreciation_amortization",
            ),
            "ebitda": (
                "ebitda_ttm",
            ),
        }

        for canonical, candidates in aliases.items():

            if normalized.get(canonical) is not None:
                continue

            for alias in candidates:

                value = normalized.get(alias)

                if value is not None:
                    normalized[canonical] = value
                    break

        return normalized

    @staticmethod
    def _warnings(
        result: Any,
    ) -> list[str]:

        value = getattr(result, "warnings", None)

        if value is None:
            value = getattr(result, "warning", None)

        if value is None:
            value = getattr(result, "failures", None)

        if value is None:
            return []

        if isinstance(value, str):
            return [value]

        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value]

        return [str(value)]

    @staticmethod
    def _field(
        result: Any,
        name: str,
        default: Any = None,
    ) -> Any:
        return getattr(result, name, default)

    def evaluate(
        self,
        metrics: dict[str, Any],
        *,
        financial_quality: dict[str, Any] | None = None,
        market_cap: float | None = None,
        enterprise_value: float | None = None,
        price: float | None = None,
        ticker: str | None = None,
        company_name: str | None = None,
    ) -> dict[str, Any]:

        return self.analyze(
            metrics,
            financial_quality=financial_quality,
            market_cap=market_cap,
            enterprise_value=enterprise_value,
            price=price,
            ticker=ticker,
            company_name=company_name,
        )

    def analyze(
        self,
        metrics: dict[str, Any],
        *,
        financial_quality: dict[str, Any] | None = None,
        market_cap: float | None = None,
        enterprise_value: float | None = None,
        price: float | None = None,
        ticker: str | None = None,
        company_name: str | None = None,
    ) -> dict[str, Any]:

        normalized = self._normalize_metrics(metrics)

        # ------------------------------------------------------------
        # MARKET CAP FALLBACK
        # ------------------------------------------------------------

        if market_cap is None:

            for key in (
                "market_cap",
                "market_capitalization",
                "equity_value",
            ):

                value = normalized.get(key)

                if value is not None:
                    market_cap = value
                    break

        # ------------------------------------------------------------
        # ENTERPRISE VALUE FALLBACK
        # ------------------------------------------------------------

        if enterprise_value is None:

            for key in (
                "enterprise_value",
                "ev",
            ):

                value = normalized.get(key)

                if value is not None:
                    enterprise_value = value
                    break

        # ------------------------------------------------------------
        # SCREENING
        # ------------------------------------------------------------

        screening = self.screening.evaluate(
            normalized,
            market_cap=market_cap,
            price=price,
        )

        # ------------------------------------------------------------
        # QUALITY
        # ------------------------------------------------------------

        quality = self.quality.calculate(
            normalized,
            financial_quality,
        )

        # ------------------------------------------------------------
        # VALUATION
        # ------------------------------------------------------------

        valuation = self.valuation.calculate(
            normalized,
            market_cap=market_cap,
            enterprise_value=enterprise_value,
        )

        # ------------------------------------------------------------
        # RISK
        # ------------------------------------------------------------

        risk = self.risk.calculate(
            normalized,
            valuation_score=valuation.score,
            financial_quality=financial_quality,
        )

        # ------------------------------------------------------------
        # NORMALIZED COMPONENT SCORES
        # ------------------------------------------------------------

        screening_score = float(
            self._field(screening, "score", 0.0)
            or 0.0
        )

        quality_score = float(
            self._field(quality, "score", 0.0)
            or 0.0
        )

        valuation_score = float(
            self._field(valuation, "score", 0.0)
            or 0.0
        )

        risk_score = float(
            self._field(risk, "score", 0.0)
            or 0.0
        )

        # ------------------------------------------------------------
        # FINAL ATLAS SCORE
        # ------------------------------------------------------------

        final_score = (
            screening_score * 0.20
            + quality_score * 0.30
            + valuation_score * 0.25
            + risk_score * 0.25
        )

        final_score = max(
            0.0,
            min(100.0, final_score),
        )

        final_score = round(
            final_score,
            4,
        )

        # ------------------------------------------------------------
        # INVESTMENT DECISION
        #
        # Mega F public contract:
        # PASS / WATCH / REJECT
        # ------------------------------------------------------------

        if final_score >= 75:

            decision = "PASS"

        elif final_score >= 55:

            decision = "WATCH"

        else:

            decision = "REJECT"

        # ------------------------------------------------------------
        # QUALITY CONTRACT NORMALIZATION
        # ------------------------------------------------------------

        completeness = self._field(
            quality,
            "completeness",
            None,
        )

        if completeness is None:
            completeness = self._field(
                quality,
                "data_completeness",
                None,
            )

        if completeness is None:
            completeness = (
                financial_quality.get(
                    "completeness"
                )
                if financial_quality
                else 0.0
            )

        confidence = self._field(
            quality,
            "confidence",
            None,
        )

        if confidence is None:
            confidence = (
                financial_quality.get(
                    "confidence",
                    "UNKNOWN",
                )
                if financial_quality
                else "UNKNOWN"
            )

        # ------------------------------------------------------------
        # RISK CONTRACT NORMALIZATION
        # ------------------------------------------------------------

        financial_risk = self._field(
            risk,
            "financial_risk",
            0.0,
        )

        valuation_risk = self._field(
            risk,
            "valuation_risk",
            0.0,
        )

        # ------------------------------------------------------------
        # RESULT
        # ------------------------------------------------------------

        return {

            "status": "success",

            "stage": "investment_decision",

            "ticker": ticker,

            "company_name": company_name,

            # --------------------------------------------------------
            # SCREENING
            # --------------------------------------------------------

            "screening": {

                "score": screening_score,

                "passed": bool(
                    self._field(
                        screening,
                        "passed",
                        False,
                    )
                ),

                "warnings": self._warnings(
                    screening
                ),

            },

            # --------------------------------------------------------
            # QUALITY
            # --------------------------------------------------------

            "quality": {

                "score": quality_score,

                "completeness": completeness,

                "confidence": confidence,

                "warnings": self._warnings(
                    quality
                ),

            },

            # --------------------------------------------------------
            # VALUATION
            # --------------------------------------------------------

            "valuation": {

                "score": valuation_score,

                "pe": self._field(
                    valuation,
                    "pe",
                ),

                "ev_ebitda": self._field(
                    valuation,
                    "ev_ebitda",
                ),

                "price_to_fcf": self._field(
                    valuation,
                    "price_to_fcf",
                ),

                "fcf_yield": self._field(
                    valuation,
                    "fcf_yield",
                ),

                "earnings_yield": self._field(
                    valuation,
                    "earnings_yield",
                ),

                "margin_of_safety": self._field(
                    valuation,
                    "margin_of_safety",
                ),

                "warnings": self._warnings(
                    valuation
                ),

            },

            # --------------------------------------------------------
            # RISK
            # --------------------------------------------------------

            "risk": {

                "score": risk_score,

                "financial_risk": financial_risk,

                "valuation_risk": valuation_risk,

                "warnings": self._warnings(
                    risk
                ),

            },

            # --------------------------------------------------------
            # FINAL
            # --------------------------------------------------------

            "final_score": final_score,

            "atlas_score": final_score,

            "decision": decision,

        }


InvestmentEngine = InvestmentDecisionEngine

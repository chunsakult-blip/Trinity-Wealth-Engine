from __future__ import annotations

from dataclasses import dataclass

from ai.research.sec.sec_client import SECClient

from ai.research.financial.financial_normalizer_v4 import (
    FinancialNormalizerV4,
)

from ai.research.investment.engine import (
    InvestmentDecisionEngine,
)


@dataclass
class AnalysisResult:

    ticker: str

    quality_score: float

    valuation_score: float

    total_score: float

    rating: str

    decision: str = ""

    screening_score: float = 0.0

    risk_score: float = 0.0


class FinancialAnalysisPipeline:

    """
    Canonical financial analysis boundary.

    Runtime chain:

        SEC
          ↓
        FinancialNormalizerV4
          ↓
        NormalizedFinancials
          ↓
        InvestmentDecisionEngine
          ↓
        Screening / Quality / Valuation / Risk
          ↓
        ATLAS score + decision

    Legacy FinancialQualityEngine,
    InvestmentRanker and legacy quality_score
    are intentionally NOT used here.
    """

    def __init__(self):

        self.sec = SECClient(
            user_agent=
            "Trinity-Wealth-Engine contact@example.com"
        )

        self.normalizer = (
            FinancialNormalizerV4()
        )

        self.decision_engine = (
            InvestmentDecisionEngine()
        )

    def analyze(
        self,
        cik: str,
        ticker: str,
        price: float,
        shares: float,
    ) -> AnalysisResult:

        # -----------------------------------------------------
        # SEC
        # -----------------------------------------------------

        sec_data = (
            self.sec
            .get_company_facts(cik)
        )

        # -----------------------------------------------------
        # CANONICAL NORMALIZATION
        # -----------------------------------------------------

        financials = (
            self.normalizer
            .normalize(
                sec_data.payload,
                cik=int(cik),
                ticker=ticker,
            )
        )

        # -----------------------------------------------------
        # TTM COMPATIBILITY CHECK
        # -----------------------------------------------------

        ttm = getattr(
            financials,
            "ttm",
            None,
        )

        if ttm is None:
            raise RuntimeError(
                f"No TTM data for {ticker}"
            )

        # -----------------------------------------------------
        # MARKET CAP
        #
        # Existing pipeline contract supplies:
        # price + shares
        #
        # Preserve that boundary while moving scoring
        # completely into the canonical engine.
        # -----------------------------------------------------

        market_cap = None

        try:
            market_cap = (
                float(price)
                * float(shares)
            )
        except (
            TypeError,
            ValueError,
        ):
            market_cap = None

        # -----------------------------------------------------
        # CANONICAL INVESTMENT DECISION
        # -----------------------------------------------------

        decision = (
            self.decision_engine
            .analyze(
                ttm,
                market_cap=market_cap,
                price=price,
                ticker=ticker,
            )
        )

        if not isinstance(
            decision,
            dict,
        ):
            raise RuntimeError(
                f"Canonical decision engine returned "
                f"invalid result for {ticker}: "
                f"{type(decision).__name__}"
            )

        if decision.get("status") != "success":
            raise RuntimeError(
                f"Canonical decision failed for {ticker}: "
                f"{decision}"
            )

        # -----------------------------------------------------
        # COMPONENT SCORES
        # -----------------------------------------------------

        quality = (
            decision.get(
                "quality",
                {},
            )
            or {}
        )

        valuation = (
            decision.get(
                "valuation",
                {},
            )
            or {}
        )

        screening = (
            decision.get(
                "screening",
                {},
            )
            or {}
        )

        risk = (
            decision.get(
                "risk",
                {},
            )
            or {}
        )

        quality_score = float(
            quality.get(
                "score",
                0.0,
            )
            or 0.0
        )

        valuation_score = float(
            valuation.get(
                "score",
                0.0,
            )
            or 0.0
        )

        screening_score = float(
            screening.get(
                "score",
                0.0,
            )
            or 0.0
        )

        risk_score = float(
            risk.get(
                "score",
                0.0,
            )
            or 0.0
        )

        total_score = float(
            decision.get(
                "final_score",
                decision.get(
                    "atlas_score",
                    0.0,
                ),
            )
            or 0.0
        )

        canonical_decision = str(
            decision.get(
                "decision",
                "REJECT",
            )
        )

        # -----------------------------------------------------
        # CANONICAL RATING
        #
        # The canonical InvestmentDecisionEngine is the single
        # source of truth for investment outcome semantics.
        #
        # PASS   = acceptable investment candidate
        # WATCH  = monitor
        # REJECT = rejected
        #
        # Do NOT translate REJECT -> PASS or PASS -> BUY.
        # Such translation belonged to the legacy ranking layer
        # and creates contradictory public results.
        # -----------------------------------------------------

        rating = canonical_decision

        return AnalysisResult(

            ticker=ticker,

            quality_score=quality_score,

            valuation_score=valuation_score,

            total_score=round(
                total_score,
                4,
            ),

            rating=rating,

            decision=canonical_decision,

            screening_score=screening_score,

            risk_score=risk_score,
        )

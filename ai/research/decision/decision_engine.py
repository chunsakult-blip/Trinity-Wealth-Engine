from __future__ import annotations

from dataclasses import dataclass

from ai.research.financial.quality_score import (
    FinancialQualityScore,
)

from ai.research.investor.investor_signal import (
    InvestorSignal,
)

from ai.research.valuation.valuation_engine import (
    ValuationResult,
)



@dataclass
class TrinityDecision:

    ticker: str

    trinity_score: float

    action: str

    reasons: list[str]



class TrinityDecisionEngine:


    def evaluate(

        self,

        ticker: str,

        quality: FinancialQualityScore,

        valuation: ValuationResult,

        investor: InvestorSignal,

    ) -> TrinityDecision:


        score = (

            quality.total * 0.4

            +

            valuation.score * 0.35

            +

            investor.total_score * 0.25

        )


        reasons = []


        if quality.total >= 70:
            reasons.append(
                "High financial quality"
            )


        if valuation.score >= 70:
            reasons.append(
                "Attractive valuation"
            )


        if investor.total_score >= 70:
            reasons.append(
                "Strong investor signal"
            )


        if score >= 80:

            action = "STRONG BUY"

        elif score >= 65:

            action = "BUY"

        elif score >= 50:

            action = "WATCH"

        else:

            action = "PASS"



        return TrinityDecision(

            ticker=ticker,

            trinity_score=round(
                score,
                2
            ),

            action=action,

            reasons=reasons,

        )

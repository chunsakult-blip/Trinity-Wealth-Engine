from __future__ import annotations

from dataclasses import dataclass


from ai.research.financial.quality_score import (
    FinancialQualityScore,
)

from ai.research.valuation.valuation_engine import (
    ValuationResult,
)



@dataclass
class InvestmentRank:

    total_score: float

    quality_score: float

    valuation_score: float

    rating: str



class InvestmentRanker:



    def calculate(

        self,

        quality: FinancialQualityScore,

        valuation: ValuationResult,

    ) -> InvestmentRank:



        quality_score = (
            quality.total
        )


        valuation_score = (
            valuation.score
        )



        total = (

            quality_score * 0.6

            +

            valuation_score * 0.4

        )



        if total >= 80:

            rating="STRONG BUY"


        elif total >= 65:

            rating="BUY"


        elif total >= 50:

            rating="WATCH"


        else:

            rating="PASS"



        return InvestmentRank(

            total_score=round(total,2),

            quality_score=quality_score,

            valuation_score=valuation_score,

            rating=rating,

        )

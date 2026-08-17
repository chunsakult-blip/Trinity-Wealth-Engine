from __future__ import annotations

from dataclasses import dataclass



@dataclass
class RankedStockV2:

    ticker: str
    name: str

    growth_score: float
    financial_score: float
    investor_score: float
    valuation_score: float

    final_score: float

    rating: str

    reasons: list[str]



class MasterRankerV2:


    def calculate(
        self,
        candidate,
        financial,
        investor,
        valuation,
    ):


        growth = (
            candidate.score
        )


        financial_score = (
            financial.quality_score
        )


        investor_score = (
            investor.total_score
        )


        valuation_score = (
            valuation.valuation_score
        )



        final = (

            growth * 0.25

            +

            financial_score * 0.35

            +

            investor_score * 0.20

            +

            valuation_score * 0.20

        )



        reasons=[]



        if growth >= 70:

            reasons.append(
                "High growth profile"
            )



        if financial_score >= 70:

            reasons.append(
                "Strong financial quality"
            )



        if investor_score >= 50:

            reasons.append(
                "Institutional support"
            )



        if valuation_score >= 80:

            reasons.append(
                "Attractive valuation"
            )



        if final >= 85:

            rating="STRONG BUY"


        elif final >= 70:

            rating="BUY"


        elif final >= 55:

            rating="WATCH"


        else:

            rating="PASS"



        return RankedStockV2(

            ticker=candidate.ticker,

            name=candidate.name,

            growth_score=growth,

            financial_score=financial_score,

            investor_score=investor_score,

            valuation_score=valuation_score,

            final_score=round(
                final,
                2
            ),

            rating=rating,

            reasons=reasons,

        )




    def rank(
        self,
        stocks
    ):

        return sorted(
            stocks,
            key=lambda x:x.final_score,
            reverse=True
        )


from __future__ import annotations

from dataclasses import dataclass



@dataclass
class RankedStock:

    ticker: str
    name: str

    growth_score: float
    financial_score: float
    investor_score: float

    total_score: float

    action: str



class MasterRanker:


    def calculate(
        self,
        candidate,
        financial,
        investor_score: float = 0,
    ):


        growth = candidate.score


        quality = (
            financial.quality_score
        )


        total = (

            growth * 0.35

            +

            quality * 0.45

            +

            investor_score * 0.20

        )


        if total >= 80:

            action="STRONG BUY"


        elif total >= 65:

            action="BUY"


        elif total >= 50:

            action="WATCH"


        else:

            action="PASS"



        return RankedStock(

            ticker=candidate.ticker,

            name=candidate.name,

            growth_score=growth,

            financial_score=quality,

            investor_score=investor_score,

            total_score=round(
                total,
                2
            ),

            action=action,

        )



    def rank(
        self,
        stocks,
    ):

        return sorted(
            stocks,
            key=lambda x:x.total_score,
            reverse=True
        )


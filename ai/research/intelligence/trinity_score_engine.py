from __future__ import annotations

from dataclasses import dataclass



@dataclass
class TrinityScore:

    ticker:str

    growth:float

    financial:float

    valuation:float

    smart_money:float

    total:float

    action:str




class TrinityScoreEngine:



    def calculate(
        self,
        ticker:str,
        growth:float,
        financial:float,
        valuation:float,
        smart_money:float
    ):


        total=(

            growth * 0.30

            +

            financial * 0.30

            +

            valuation * 0.25

            +

            smart_money * 0.15

        )



        if total >= 85:

            action="STRONG BUY"

        elif total >=70:

            action="BUY"

        elif total >=55:

            action="WATCH"

        else:

            action="PASS"



        return TrinityScore(

            ticker=ticker,

            growth=growth,

            financial=financial,

            valuation=valuation,

            smart_money=smart_money,

            total=round(
                total,
                2
            ),

            action=action

        )




class InstitutionalSignalEngine:



    def calculate(
        self,
        holdings_change:float,
        fund_count:int
    ):


        score=0



        if holdings_change > 0:

            score += 50



        if fund_count >= 20:

            score += 50

        elif fund_count >= 5:

            score += 25



        return min(
            score,
            100
        )


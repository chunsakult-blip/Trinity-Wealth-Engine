from __future__ import annotations

from dataclasses import dataclass



@dataclass
class ValuationResult:

    ticker:str

    valuation_score:float

    margin_of_safety:float

    rating:str




class ValuationEngine:



    def calculate(
        self,
        ticker:str,
        revenue:float,
        net_income:float,
        cashflow:float,
        market_cap:float,
        growth:float
    ):


        score=0



        # profitability

        if net_income > 0:

            score += 25



        # cash generation

        if cashflow > 0:

            score += 25



        # growth quality

        if growth >= 15:

            score += 30

        elif growth >= 5:

            score += 15



        # valuation multiple

        if market_cap > 0 and net_income > 0:

            pe = market_cap / net_income

            if pe < 20:

                score += 20

            elif pe < 40:

                score += 10



        score=min(
            score,
            100
        )


        if score >= 80:

            rating="UNDERVALUED"

        elif score >= 60:

            rating="FAIR VALUE"

        else:

            rating="EXPENSIVE"



        margin = max(
            0,
            100-score
        )



        return ValuationResult(

            ticker=ticker,

            valuation_score=score,

            margin_of_safety=margin,

            rating=rating

        )


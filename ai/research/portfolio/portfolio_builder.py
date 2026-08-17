from __future__ import annotations

from dataclasses import dataclass



@dataclass
class PortfolioPosition:

    ticker:str
    score:float
    allocation:float
    risk:str



class PortfolioBuilder:



    def __init__(self):

        self.max_position = 15



    def risk_level(
        self,
        score
    ):

        if score >=85:
            return "LOW"

        elif score >=70:
            return "MEDIUM"

        else:
            return "HIGH"



    def build(
        self,
        ranked_stocks,
        capital=1000000,
        limit=10
    ):


        selected = ranked_stocks[:limit]


        total_score = sum(
            x.total_score
            for x in selected
        )


        portfolio=[]


        for stock in selected:


            weight = (
                stock.total_score
                /
                total_score
                *
                100
            )


            if weight > self.max_position:
                weight=self.max_position


            portfolio.append(

                PortfolioPosition(

                    ticker=stock.ticker,

                    score=stock.total_score,

                    allocation=round(
                        weight,
                        2
                    ),

                    risk=self.risk_level(
                        stock.total_score
                    )

                )

            )


        return portfolio


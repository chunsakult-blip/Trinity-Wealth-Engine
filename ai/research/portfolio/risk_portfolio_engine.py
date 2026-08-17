from __future__ import annotations

from dataclasses import dataclass



@dataclass
class PortfolioPosition:

    ticker:str
    score:float
    risk:float
    weight:float
    action:str




class RiskPortfolioEngine:


    def __init__(self):

        self.max_position = 0.15



    def calculate_risk(
        self,
        stock
    ):

        risk = 100 - stock.total_score

        if risk < 10:
            risk = 10

        return min(
            risk,
            100
        )



    def allocate(
        self,
        stocks
    ):


        results=[]


        total_score = sum(
            s.total_score
            for s in stocks
        )


        for stock in stocks:


            weight = (
                stock.total_score /
                total_score
            )


            weight=min(
                weight,
                self.max_position
            )


            risk=self.calculate_risk(
                stock
            )


            if risk < 25:
                action="ACCUMULATE"

            elif risk < 50:
                action="HOLD"

            else:
                action="REDUCE"



            results.append(

                PortfolioPosition(

                    ticker=stock.ticker,

                    score=stock.total_score,

                    risk=risk,

                    weight=round(
                        weight,
                        4
                    ),

                    action=action

                )

            )


        return results



    def summary(
        self,
        portfolio
    ):


        return {

            "positions":
                len(portfolio),

            "allocation":
            {
                p.ticker:
                p.weight

                for p in portfolio
            },

            "risk":
            {
                p.ticker:
                p.risk

                for p in portfolio
            }

        }


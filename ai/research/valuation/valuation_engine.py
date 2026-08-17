from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValuationScore:

    ticker: str

    valuation_score: float

    margin_of_safety: float

    level: str

    reasons: list[str]



class ValuationEngine:


    def calculate(
        self,
        financial,
    ):

        score = 50

        reasons=[]


        revenue = financial.revenue

        income = financial.net_income


        if revenue > 0:

            margin = (
                income / revenue
            )

            if margin > 0.20:

                score += 20

                reasons.append(
                    "High profitability"
                )

            elif margin < 0:

                score -= 30

                reasons.append(
                    "Negative margin"
                )


        if financial.assets > financial.liabilities:

            score += 10

            reasons.append(
                "Healthy balance sheet"
            )


        if financial.cashflow > 0:

            score += 10

            reasons.append(
                "Positive operating cashflow"
            )


        score = max(
            min(score,100),
           0
        )


        if score >= 80:

            level="UNDERVALUED"

        elif score >=60:

            level="FAIR VALUE"

        else:

            level="OVERVALUED"



        return ValuationScore(

            ticker=financial.ticker,

            valuation_score=score,

            margin_of_safety=score,

            level=level,

            reasons=reasons

        )


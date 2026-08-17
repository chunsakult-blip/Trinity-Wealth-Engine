from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskScore:

    ticker: str
    risk_score: float
    level: str
    reasons: list[str]



class RiskEngine:


    def calculate(
        self,
        financial
    ):


        score = 0

        reasons=[]


        # profitability risk

        if financial.net_income <= 0:

            score += 30

            reasons.append(
                "Negative earnings"
            )


        # balance sheet risk

        if (
            financial.liabilities
            >
            financial.assets
        ):

            score += 30

            reasons.append(
                "Weak balance sheet"
            )


        # cashflow risk

        if financial.cashflow <= 0:

            score += 25

            reasons.append(
                "Negative operating cashflow"
            )


        # low data confidence

        if financial.revenue <= 0:

            score += 15

            reasons.append(
                "Missing revenue data"
            )



        if score >= 70:

            level="HIGH"


        elif score >= 40:

            level="MEDIUM"


        else:

            level="LOW"



        return RiskScore(

            ticker=financial.ticker,

            risk_score=min(
                score,
                100
            ),

            level=level,

            reasons=reasons

        )

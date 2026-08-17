from __future__ import annotations

from dataclasses import dataclass



@dataclass
class AnalystReport:

    ticker:str

    conclusion:str

    strengths:list[str]

    risks:list[str]

    confidence:float




class InvestmentAnalystAgent:



    def analyze(
        self,
        stock,
        financial,
        portfolio=None
    ):


        strengths=[]

        risks=[]



        if stock.growth_score >= 70:

            strengths.append(
                "High growth potential"
            )

        else:

            risks.append(
                "Limited growth signal"
            )



        if stock.financial_score >= 70:

            strengths.append(
                "Strong financial quality"
            )

        else:

            risks.append(
                "Financial quality concern"
            )



        if stock.total_score >= 80:

            conclusion="STRONG BUY"

        elif stock.total_score >= 65:

            conclusion="BUY"

        elif stock.total_score >= 50:

            conclusion="WATCH"

        else:

            conclusion="PASS"



        confidence=min(

            stock.total_score,

            100

        )



        return AnalystReport(

            ticker=stock.ticker,

            conclusion=conclusion,

            strengths=strengths,

            risks=risks,

            confidence=confidence

        )


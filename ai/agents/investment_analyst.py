from __future__ import annotations

from dataclasses import dataclass



@dataclass
class AnalystReport:

    ticker:str

    conclusion:str

    strengths:list[str]

    risks:list[str]

    confidence:float



class InvestmentAnalyst:



    def analyze(
        self,
        stock
    ):


        strengths=[]

        risks=[]



        score = stock.final_score



        if stock.growth_score >= 70:

            strengths.append(
                "Strong growth profile"
            )


        elif stock.growth_score >= 50:

            strengths.append(
                "Positive growth signal"
            )


        else:

            risks.append(
                "Limited growth signal"
            )



        if stock.financial_score >= 70:

            strengths.append(
                "High financial quality"
            )


        else:

            risks.append(
                "Financial quality concern"
            )



        if stock.valuation_score >= 80:

            strengths.append(
                "Attractive valuation"
            )


        elif stock.valuation_score < 50:

            risks.append(
                "Expensive valuation"
            )



        if stock.investor_score >= 50:

            strengths.append(
                "Institutional support"
            )



        if score >= 85:

            conclusion="STRONG BUY"

        elif score >=70:

            conclusion="BUY"

        elif score >=55:

            conclusion="WATCH"

        else:

            conclusion="PASS"



        confidence = min(
            round(score * 0.8,1),
            100
        )



        return AnalystReport(

            ticker=stock.ticker,

            conclusion=conclusion,

            strengths=strengths,

            risks=risks,

            confidence=confidence,

        )


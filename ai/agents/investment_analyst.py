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
        portfolio=None
    ):


        strengths=[]

        risks=[]



        score = getattr(
            stock,
            "final_score",
            0
        )


        growth = getattr(
            stock,
            "growth_score",
            0
        )


        financial = getattr(
            stock,
            "financial_score",
            0
        )


        valuation = getattr(
            stock,
            "valuation_score",
            0
        )


        investor = getattr(
            stock,
            "investor_score",
            0
        )



        if growth >= 70:

            strengths.append(
                "Strong growth profile"
            )

        else:

            risks.append(
                "Limited growth signal"
            )



        if financial >= 70:

            strengths.append(
                "High financial quality"
            )

        else:

            risks.append(
                "Financial quality concern"
            )



        if investor >= 50:

            strengths.append(
                "Institutional support"
            )



        if valuation >= 80:

            strengths.append(
                "Attractive valuation"
            )

        else:

            risks.append(
                "Valuation not attractive"
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
            round(score * 0.9,2),
            95
        )



        return AnalystReport(

            ticker=stock.ticker,

            conclusion=conclusion,

            strengths=strengths,

            risks=risks,

            confidence=confidence

        )



InvestmentAnalyst = InvestmentAnalystAgent


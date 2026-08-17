from __future__ import annotations

from dataclasses import dataclass



@dataclass
class AnalystReport:

    ticker:str
    summary:str
    recommendation:str
    confidence:int



class AnalystEngine:



    def __init__(
        self,
        model="local"
    ):

        self.model=model



    def analyze(
        self,
        ticker,
        growth_score,
        financial_score,
        risk_score
    ):


        total=(

            growth_score*0.4

            +

            financial_score*0.4

            +

            risk_score*0.2

        )



        if total>=80:

            recommendation="BUY"

        elif total>=60:

            recommendation="WATCH"

        else:

            recommendation="PASS"



        summary=(

            f"{ticker} analysis: "

            f"Growth={growth_score}, "

            f"Financial={financial_score}, "

            f"Risk={risk_score}"

        )



        return AnalystReport(

            ticker=ticker,

            summary=summary,

            recommendation=recommendation,

            confidence=int(total)

        )


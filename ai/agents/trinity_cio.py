from __future__ import annotations

from dataclasses import dataclass



@dataclass
class CIODecision:

    ticker:str

    decision:str

    confidence:float

    thesis:list[str]

    risks:list[str]

    allocation:str



class TrinityCIO:



    def decide(
        self,
        ticker,
        score,
        growth,
        financial,
        valuation,
        smart_money
    ):


        thesis=[]
        risks=[]


        if growth >=80:

            thesis.append(
                "Exceptional growth profile"
            )

        else:

            risks.append(
                "Growth slowdown risk"
            )



        if financial >=80:

            thesis.append(
                "Strong balance sheet"
            )

        else:

            risks.append(
                "Financial weakness"
            )



        if smart_money >=70:

            thesis.append(
                "Institutional accumulation"
            )

        else:

            risks.append(
                "Weak institutional signal"
            )



        if score >=85:

            decision="BUY"

            allocation="CORE POSITION"

            confidence=90


        elif score >=70:

            decision="WATCH BUY"

            allocation="SMALL POSITION"

            confidence=70


        else:

            decision="PASS"

            allocation="NO POSITION"

            confidence=40



        return CIODecision(

            ticker=ticker,

            decision=decision,

            confidence=confidence,

            thesis=thesis,

            risks=risks,

            allocation=allocation

        )


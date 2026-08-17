from __future__ import annotations

from dataclasses import dataclass



@dataclass
class InvestmentMemo:

    ticker:str

    score:float

    rating:str

    thesis:list[str]

    risks:list[str]

    action:str




class InvestmentMemoEngine:



    def generate(
        self,
        ticker:str,
        score:float,
        growth:float,
        financial:float,
        valuation:float,
        smart_money:float
    ):


        thesis=[]

        risks=[]



        if growth >=70:

            thesis.append(
                "Strong growth characteristics"
            )

        else:

            risks.append(
                "Growth momentum weakness"
            )



        if financial >=70:

            thesis.append(
                "High financial quality"
            )

        else:

            risks.append(
                "Financial quality concern"
            )



        if valuation >=70:

            thesis.append(
                "Attractive valuation profile"
            )

        else:

            risks.append(
                "Valuation risk"
            )



        if smart_money >=70:

            thesis.append(
                "Institutional accumulation signal"
            )

        else:

            risks.append(
                "Weak institutional interest"
            )



        if score >=85:

            rating="A"

            action="ACCUMULATE"



        elif score >=70:

            rating="B"

            action="BUY WATCH"



        elif score >=55:

            rating="C"

            action="MONITOR"



        else:

            rating="D"

            action="AVOID"



        return InvestmentMemo(

            ticker=ticker,

            score=score,

            rating=rating,

            thesis=thesis,

            risks=risks,

            action=action

        )


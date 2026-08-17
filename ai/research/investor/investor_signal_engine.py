from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InvestorSignal:

    ticker: str

    institutional_score: float
    ownership_score: float
    momentum_score: float

    total_score: float

    signals: list[str]



class InvestorSignalEngine:


    def __init__(self):

        self.priority_investors = {

            "BERKSHIRE",
            "BLACKROCK",
            "VANGUARD",
            "FIDELITY",
            "STATE STREET",

        }



    def analyze(
        self,
        ticker:str,
        institutional_data:dict | None = None,
    ):


        score = 0

        signals=[]


        institutional_score=0
        ownership_score=0
        momentum_score=0



        if institutional_data:


            investors = (
                institutional_data
                .get("investors",[])
            )


            for investor in investors:


                name = investor.upper()


                for priority in self.priority_investors:


                    if priority in name:

                        institutional_score += 20

                        signals.append(
                            f"Smart money: {priority}"
                        )

                        break



        if ticker in {

            "NVDA",
            "MSFT",
            "GOOGL",
            "AMZN",
            "META",
            "AVGO",

        }:

            ownership_score += 40

            signals.append(
                "Institutional compounder"
            )



        momentum_score = 30



        total = (

            institutional_score * 0.4

            +

            ownership_score * 0.4

            +

            momentum_score * 0.2

        )


        return InvestorSignal(

            ticker=ticker,

            institutional_score=institutional_score,

            ownership_score=ownership_score,

            momentum_score=momentum_score,

            total_score=min(
                round(total,2),
                100
            ),

            signals=signals,

        )


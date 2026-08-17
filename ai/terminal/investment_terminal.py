from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime



@dataclass
class TerminalReport:

    created:str
    total_stocks:int
    top_pick:str
    action:str
    summary:str




class InvestmentTerminal:



    def generate(
        self,
        stocks
    ):


        if not stocks:

            return TerminalReport(

                created=str(datetime.now()),

                total_stocks=0,

                top_pick="NONE",

                action="WAIT",

                summary="No signal"

            )



        top=stocks[0]



        return TerminalReport(

            created=str(datetime.now()),

            total_stocks=len(stocks),

            top_pick=top.ticker,

            action=getattr(
                top,
                "action",
                "WATCH"
            ),

            summary=(

                f"Top candidate {top.ticker} "

                f"score={top.total_score}"

            )

        )


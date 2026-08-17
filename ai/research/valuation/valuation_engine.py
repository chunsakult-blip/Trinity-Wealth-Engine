from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValuationResult:

    pe: Optional[float] = None

    pfcf: Optional[float] = None

    score: float = 0



class ValuationEngine:


    def calculate(

        self,

        price: float,

        shares: float,

        net_income: float | None,

        free_cash_flow: float | None,

    ) -> ValuationResult:


        market_cap = (
            price * shares
        )


        pe = None

        pfcf = None


        score = 0



        if (
            net_income
            and net_income > 0
        ):

            pe = (
                market_cap /
                net_income
            )


            if pe < 15:
                score += 50

            elif pe < 25:
                score += 25



        if (
            free_cash_flow
            and free_cash_flow > 0
        ):

            pfcf = (
                market_cap /
                free_cash_flow
            )


            if pfcf < 20:
                score += 50

            elif pfcf < 35:
                score += 25



        return ValuationResult(

            pe=pe,

            pfcf=pfcf,

            score=score,

        )

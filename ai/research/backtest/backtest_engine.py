from __future__ import annotations

from dataclasses import dataclass



@dataclass
class BacktestResult:

    ticker:str
    start_value:float
    end_value:float
    return_pct:float
    max_drawdown:float
    grade:str



class BacktestEngine:



    def simulate(
        self,
        ticker,
        prices,
        capital=100000
    ):


        if not prices:

            return None



        peak=capital

        max_drawdown=0



        value=capital



        for change in prices:

            value *= (
                1 + change
            )


            if value > peak:

                peak=value


            drawdown=(

                peak-value

            )/peak*100


            if drawdown > max_drawdown:

                max_drawdown=drawdown



        result=(

            value-capital

        )/capital*100



        if result >=50:

            grade="A"

        elif result >=20:

            grade="B"

        else:

            grade="C"



        return BacktestResult(

            ticker=ticker,

            start_value=capital,

            end_value=round(
                value,
                2
            ),

            return_pct=round(
                result,
                2
            ),

            max_drawdown=round(
                max_drawdown,
                2
            ),

            grade=grade

        )


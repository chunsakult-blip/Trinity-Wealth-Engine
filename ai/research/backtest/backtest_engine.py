from __future__ import annotations

from dataclasses import dataclass



@dataclass
class BacktestResult:

    ticker:str

    initial:float
    final:float

    return_pct:float

    win:bool




class BacktestEngine:



    def simulate(
        self,
        ticker:str,
        prices:list[float],
        capital:float=10000
    ):


        if not prices:

            raise ValueError(
                "No price data"
            )


        shares = (
            capital /
            prices[0]
        )


        final_value = (
            shares *
            prices[-1]
        )


        result = (
            (final_value-capital)
            /
            capital
        ) * 100



        return BacktestResult(

            ticker=ticker,

            initial=capital,

            final=round(
                final_value,
                2
            ),

            return_pct=round(
                result,
                2
            ),

            win=result > 0

        )



    def compare(
        self,
        results
    ):


        return sorted(

            results,

            key=lambda x:x.return_pct,

            reverse=True

        )


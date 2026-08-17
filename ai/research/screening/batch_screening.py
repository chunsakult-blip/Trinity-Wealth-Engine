from __future__ import annotations

from dataclasses import dataclass
from typing import List


from ai.research.universe.us_market_universe import (
    USMarketUniverse,
)

from ai.research.pipeline.financial_pipeline import (
    FinancialAnalysisPipeline,
)


@dataclass
class ScreeningResult:

    ticker: str
    score: float
    rating: str



class BatchScreeningEngine:


    def __init__(self):

        self.universe = USMarketUniverse()

        self.pipeline = (
            FinancialAnalysisPipeline()
        )


    def screen_seed(
        self,
    ) -> List[ScreeningResult]:

        stocks = (
            self.universe
            .load_seed()
        )


        results = []


        for stock in stocks:

            try:

                result = (
                    self.pipeline
                    .analyze(
                        cik=stock.cik,
                        ticker=stock.ticker,
                        price=230,
                        shares=15000000000,
                    )
                )


                results.append(
                    ScreeningResult(
                        ticker=result.ticker,
                        score=result.total_score,
                        rating=result.rating,
                    )
                )


            except Exception as e:

                print(
                    f"SKIP {stock.ticker}: {e}"
                )


        results.sort(
            key=lambda x: x.score,
            reverse=True,
        )

        return results

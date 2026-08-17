from __future__ import annotations

from dataclasses import dataclass


from ai.research.sec.sec_client import SECClient

from ai.research.financial.normalizer import (
    FinancialFactNormalizer,
)

from ai.research.financial.metrics import (
    FinancialMetricsEngine,
)

from ai.research.financial.quality_score import (
    FinancialQualityEngine,
)

from ai.research.valuation.valuation_engine import (
    ValuationEngine,
)

from ai.research.ranking.investment_ranker import (
    InvestmentRanker,
)



@dataclass
class AnalysisResult:

    ticker: str

    quality_score: float

    valuation_score: float

    total_score: float

    rating: str



class FinancialAnalysisPipeline:


    def __init__(self):

        self.sec = SECClient(
            user_agent=
            "Trinity-Wealth-Engine contact@example.com"
        )

        self.normalizer = (
            FinancialFactNormalizer()
        )

        self.metrics = (
            FinancialMetricsEngine()
        )

        self.quality = (
            FinancialQualityEngine()
        )

        self.valuation = (
            ValuationEngine()
        )

        self.rank = (
            InvestmentRanker()
        )



    def analyze(

        self,

        cik: str,

        ticker: str,

        price: float,

        shares: float,

    ) -> AnalysisResult:



        sec_data = (
            self.sec
            .get_company_facts(cik)
        )



        financials = (
            self.normalizer
            .normalize(

                sec_data.payload,

                cik=int(cik),

                ticker=ticker,

            )
        )



        if financials.ttm is None:

            raise RuntimeError(
                f"No TTM data for {ticker}"
            )



        metrics = (
            self.metrics
            .calculate(

                financials.ttm

            )
        )



        quality = (
            self.quality
            .calculate(

                metrics

            )
        )



        valuation = (
            self.valuation
            .calculate(

                price=price,

                shares=shares,

                net_income=
                financials.ttm.net_income,

                free_cash_flow=
                financials.ttm.free_cash_flow,

            )
        )



        ranking = (
            self.rank
            .calculate(

                quality,

                valuation,

            )
        )



        return AnalysisResult(

            ticker=ticker,

            quality_score=
            ranking.quality_score,

            valuation_score=
            ranking.valuation_score,

            total_score=
            ranking.total_score,

            rating=
            ranking.rating,

        )

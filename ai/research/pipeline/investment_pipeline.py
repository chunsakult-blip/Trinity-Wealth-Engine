from __future__ import annotations


from ai.research.universe.sec_market_loader import (
    SECMarketLoader
)

from ai.research.universe.growth_universe_v3 import (
    GrowthUniverseV3Builder
)

from ai.research.financial.financial_intelligence import (
    FinancialIntelligenceEngine
)

from ai.research.ranking.master_ranker import (
    MasterRanker
)



class InvestmentPipeline:


    def __init__(self):

        self.market_loader = SECMarketLoader()

        self.growth_builder = GrowthUniverseV3Builder()

        self.financial_engine = FinancialIntelligenceEngine()

        self.ranker = MasterRanker()



    def run(
        self,
        limit=20
    ):


        print(
            "Loading market universe..."
        )


        universe = self.market_loader.load()



        print(
            "Finding growth companies..."
        )


        candidates = (
            self.growth_builder
            .build(
                universe
            )
        )


        results=[]



        print(
            "Analyzing financial quality..."
        )



        for candidate in candidates:


            try:


                financial = (
                    self.financial_engine
                    .analyze(
                        candidate.ticker,
                        candidate.cik
                    )
                )


                # safety check
                if not hasattr(
                    financial,
                    "quality_score"
                ):
                    continue



                ranked = (
                    self.ranker.calculate(
                        candidate,
                        financial
                    )
                )


                results.append(
                    ranked
                )


            except Exception as e:

                print(
                    candidate.ticker,
                    e
                )



        results = (
            self.ranker
            .rank(
                results
            )
        )


        print(
            "Candidates:",
            len(results)
        )


        return results[:limit]

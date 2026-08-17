from __future__ import annotations


from ai.research.universe.sec_market_loader import SECMarketLoader
from ai.research.universe.growth_universe_v3 import GrowthUniverseV3Builder

from ai.research.financial.financial_intelligence import (
    FinancialIntelligenceEngine,
    FinancialMetrics
)

from ai.research.ranking.master_ranker import MasterRanker



class InvestmentPipeline:


    def __init__(self):

        self.market_loader = SECMarketLoader()

        self.growth_builder = GrowthUniverseV3Builder()

        self.financial_engine = FinancialIntelligenceEngine()

        self.ranker = MasterRanker()



    def run(self, limit=20):


        print("Loading market universe...")

        universe = self.market_loader.load()



        print("Finding growth companies...")

        candidates = self.growth_builder.build(
            universe
        )


        results=[]


        print("Analyzing financial quality...")


        for candidate in candidates:


            try:

                financial = self.financial_engine.analyze(
                    candidate.ticker,
                    candidate.cik
                )


                # FORCE CONTRACT
                if isinstance(
                    financial,
                    dict
                ):

                    financial = FinancialMetrics(
                        ticker=candidate.ticker,
                        quality_score=0
                    )



                ranked = self.ranker.calculate(
                    candidate,
                    financial
                )


                results.append(
                    ranked
                )


            except Exception as e:

                print(
                    "ERROR",
                    candidate.ticker,
                    e
                )



        results = self.ranker.rank(
            results
        )


        print(
            "Candidates:",
            len(results)
        )


        return results[:limit]


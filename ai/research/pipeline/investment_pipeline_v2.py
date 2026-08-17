from __future__ import annotations


from ai.research.universe.sec_market_loader import SECMarketLoader

from ai.research.universe.growth_universe_v3 import (
    GrowthUniverseV3Builder
)

from ai.research.financial.financial_intelligence_v2 import (
    FinancialIntelligenceV2
)

from ai.research.investor.investor_signal_engine import (
    InvestorSignalEngine
)

from ai.research.valuation.valuation_engine import (
    ValuationEngine
)

from ai.research.ranking.master_ranker_v2 import (
    MasterRankerV2
)



class InvestmentPipelineV2:


    def __init__(self):

        self.market = SECMarketLoader()

        self.growth = GrowthUniverseV3Builder()

        self.finance = FinancialIntelligenceV2()

        self.investor = InvestorSignalEngine()

        self.valuation = ValuationEngine()

        self.rank = MasterRankerV2()



    def run(
        self,
        limit=20
    ):


        universe = self.market.load()


        candidates = (
            self.growth
            .build(
                universe
            )
        )


        results=[]



        for candidate in candidates:


            try:


                financial = (
                    self.finance.fetch(
                        candidate.ticker,
                        candidate.cik
                    )
                )


                financial_score = (
                    self.finance
                    .quality_score(
                        financial
                    )
                )


                financial.quality_score = (
                    financial_score
                )



                investor = (
                    self.investor
                    .analyze(
                        candidate.ticker
                    )
                )


                valuation = (
                    self.valuation
                    .calculate(
                        financial
                    )
                )


                ranked = (
                    self.rank.calculate(
                        candidate,
                        financial,
                        investor,
                        valuation
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



        return (
            self.rank
            .rank(
                results
            )
        )[:limit]


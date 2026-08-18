from __future__ import annotations


from ai.research.universe.sec_market_loader import (
    SECMarketLoader
)

from ai.research.universe.growth_universe_v3 import (
    GrowthUniverseV3Builder
)

from ai.research.financial.financial_intelligence_v2 import (
    FinancialIntelligenceV2
)

from ai.research.financial.financial_normalizer_v4 import (
    FinancialNormalizerV4
)

from ai.research.financial.financial_quality_engine import (
    FinancialQualityEngine
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

from ai.research.decision.investment_decision_engine import (
    InvestmentDecisionEngine
)


class InvestmentPipelineV2:

    def __init__(self):

        self.market = SECMarketLoader()

        self.growth = GrowthUniverseV3Builder()

        self.finance = FinancialIntelligenceV2()

        self.normalizer = FinancialNormalizerV4()

        self.quality = FinancialQualityEngine()

        self.investor = InvestorSignalEngine()

        self.valuation = ValuationEngine()

        self.rank = MasterRankerV2()

        self.decision = InvestmentDecisionEngine()


    def run(
        self,
        limit=20
    ):

        universe = self.market.load()

        candidates = self.growth.build(
            universe
        )

        results = []


        for candidate in candidates:

            try:

                financial = self.finance.fetch(
                    candidate.ticker,
                    candidate.cik
                )


                normalized = self.normalizer.normalize(
                    financial
                )


                quality = self.quality.analyze(
                    normalized
                )


                normalized.quality_score = (
                    quality.total_score
                )


                investor = self.investor.analyze(
                    candidate.ticker
                )


                valuation = self.valuation.calculate(
                    normalized
                )


                ranked = self.rank.calculate(
                    candidate,
                    normalized,
                    investor,
                    valuation
                )


                decision = self.decision.analyze(
                    ranked
                )


                ranked.decision = (
                    decision.decision
                )

                ranked.confidence = (
                    decision.confidence
                )

                ranked.risk_level = (
                    decision.risk_level
                )

                ranked.strengths = (
                    decision.strengths
                )

                ranked.weaknesses = (
                    decision.weaknesses
                )

                ranked.data_quality = (
                    normalized.data_quality
                )


                results.append(
                    ranked
                )


            except Exception as e:

                print(
                    candidate.ticker,
                    e
                )


        ranked_results = self.rank.rank(
            results
        )


        print(
            "Candidates:",
            len(ranked_results)
        )


        return ranked_results[:limit]

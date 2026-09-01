from __future__ import annotations

from ai.research.universe.sec_market_loader import SECMarketLoader
from ai.research.universe.growth_universe_v3 import GrowthUniverseV3Builder

from ai.research.financial.engine import (
    FinancialIntelligenceEngine,
)

from ai.research.ranking.master_ranker import MasterRanker


class InvestmentPipeline:

    def __init__(self):

        self.market_loader = SECMarketLoader()

        self.growth_builder = GrowthUniverseV3Builder()

        # CANONICAL FINANCIAL ENGINE
        #
        # SEC Company Facts
        # -> FinancialFactNormalizer
        # -> NormalizedFinancials
        # -> deterministic financial metrics
        # -> FinancialQualityEngine
        #
        self.financial_engine = FinancialIntelligenceEngine()

        self.ranker = MasterRanker()


    def run(self, limit=20):

        print("Loading market universe...")

        universe = self.market_loader.load()


        print("Finding growth companies...")

        candidates = self.growth_builder.build(
            universe
        )


        results = []


        print("Analyzing financial quality...")


        for candidate in candidates:

            try:

                # ------------------------------------------------
                # CANONICAL FINANCIAL CONTRACT
                # ------------------------------------------------

                financial = self.financial_engine.analyze_company(
                    candidate.cik,
                    ticker=candidate.ticker,
                    company_name=candidate.name,
                )


                # ------------------------------------------------
                # HARD CONTRACT VALIDATION
                #
                # Do NOT silently downgrade a canonical result
                # into a deprecated compatibility object.
                # ------------------------------------------------

                if not isinstance(financial, dict):

                    raise TypeError(
                        "FinancialIntelligenceEngine returned "
                        f"{type(financial).__name__}, expected dict."
                    )


                if financial.get("status") != "success":

                    raise ValueError(
                        "Financial intelligence failed for "
                        f"{candidate.ticker}: "
                        f"{financial.get('status')}"
                    )


                quality = financial.get("quality")

                if not isinstance(quality, dict):

                    raise TypeError(
                        "Canonical financial result is missing "
                        "quality dict for "
                        f"{candidate.ticker}."
                    )


                if quality.get("score") is None:

                    raise ValueError(
                        "Canonical financial result is missing "
                        f"quality.score for {candidate.ticker}."
                    )


                # ------------------------------------------------
                # MASTER RANKER
                # ------------------------------------------------

                ranked = self.ranker.calculate(
                    candidate,
                    financial,
                )


                results.append(
                    ranked
                )


            except Exception as e:

                print(
                    "ERROR",
                    candidate.ticker,
                    repr(e),
                )


        results = self.ranker.rank(
            results
        )


        print(
            "Candidates:",
            len(results)
        )


        return results[:limit]

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ai.research.universe.sec_market_loader import (
    MarketSecurity,
)


@dataclass
class GrowthCandidateV2:

    ticker: str
    name: str
    cik: str
    score: float
    reasons: list[str]


class GrowthUniverseV2Builder:


    def __init__(self):

        self.high_growth_keywords = {

            "SEMICONDUCTOR": 40,
            "AI": 40,
            "ARTIFICIAL": 40,
            "CLOUD": 35,
            "SOFTWARE": 35,
            "CYBER": 35,
            "DATA": 30,
            "DIGITAL": 25,
            "MEDICAL": 25,
            "BIOTECH": 25,
            "HEALTH": 20,

        }


        self.priority_tickers = {

            "NVDA",
            "MSFT",
            "GOOGL",
            "AMZN",
            "META",
            "AVGO",
            "AMD",
            "TSM",
            "ASML",
            "CRM",
            "NOW",
            "ORCL",
            "ADBE",

        }



    def score(
        self,
        security: MarketSecurity,
    ) -> GrowthCandidateV2:


        ticker = security.ticker.upper()
        name = security.name.upper()


        score = 0
        reasons = []


        # ticker quality

        if len(ticker) <= 5:

            score += 10

            reasons.append(
                "US quality listing"
            )


        # sector growth

        for keyword, weight in self.high_growth_keywords.items():

            if keyword in name:

                score += weight

                reasons.append(
                    f"Sector:{keyword}"
                )

                break



        # known compounders

        if ticker in self.priority_tickers:

            score += 40

            reasons.append(
                "Growth compounder"
            )


        return GrowthCandidateV2(

            ticker=security.ticker,

            name=security.name,

            cik=security.cik,

            score=min(score,100),

            reasons=reasons,

        )



    def build(
        self,
        universe: List[MarketSecurity],
        limit: int = 500,
    ):


        results=[]


        for security in universe:

            candidate = self.score(
                security
            )


            if candidate.score >= 40:

                results.append(
                    candidate
                )


        results.sort(
            key=lambda x:x.score,
            reverse=True,
        )


        return results[:limit]

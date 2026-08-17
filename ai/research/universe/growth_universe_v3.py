from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ai.research.universe.sec_market_loader import (
    MarketSecurity,
)


@dataclass
class GrowthCandidateV3:

    ticker: str
    name: str
    cik: str
    score: float
    reasons: list[str]



class GrowthUniverseV3Builder:


    def __init__(self):

        self.core_growth = {

            "NVDA",
            "MSFT",
            "GOOGL",
            "AMZN",
            "META",
            "AVGO",
            "AMD",
            "TSM",
            "ASML",
            "ORCL",
            "CRM",
            "NOW",
            "ADBE",

        }


        self.sectors = {

            "SEMICONDUCTOR":40,
            "SOFTWARE":35,
            "CLOUD":35,
            "CYBERSECURITY":35,
            "SECURITY":25,
            "NETWORK":25,
            "DATA":25,
            "DIGITAL":20,
            "MEDICAL":20,
            "BIOTECH":20,

        }



    def calculate(
        self,
        security: MarketSecurity,
    ) -> GrowthCandidateV3:


        ticker = security.ticker.upper()
        name = security.name.upper()


        score = 0
        reasons=[]


        # quality ticker

        if (
            len(ticker)<=5
            and "-" not in ticker
        ):

            score += 10

            reasons.append(
                "Quality listing"
            )


        # sector intelligence

        for sector, weight in self.sectors.items():

            if sector in name:

                score += weight

                reasons.append(
                    sector
                )

                break



        # compounder bonus

        if ticker in self.core_growth:

            score += 40

            reasons.append(
                "Growth compounder"
            )


        return GrowthCandidateV3(

            ticker=security.ticker,

            name=security.name,

            cik=security.cik,

            score=min(score,100),

            reasons=reasons,

        )



    def build(
        self,
        universe: List[MarketSecurity],
        limit:int=300,
    ):


        candidates=[]


        for security in universe:

            item=self.calculate(
                security
            )


            if item.score>=40:

                candidates.append(
                    item
                )


        candidates.sort(
            key=lambda x:x.score,
            reverse=True
        )


        return candidates[:limit]

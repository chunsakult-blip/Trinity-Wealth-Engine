from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ai.research.universe.sec_market_loader import (
    MarketSecurity,
)


@dataclass
class GrowthCandidate:

    ticker: str
    name: str
    cik: str
    growth_score: float
    reason: list[str]


class GrowthUniverseBuilder:


    def __init__(self):

        self.priority_keywords = [
            "AI",
            "TECH",
            "SOFTWARE",
            "SEMICONDUCTOR",
            "CLOUD",
            "DATA",
            "DIGITAL",
            "HEALTH",
            "BIO",
            "MEDICAL",
        ]


    def calculate_score(
        self,
        security: MarketSecurity,
    ) -> GrowthCandidate:

        score = 0
        reasons = []

        ticker = security.ticker.upper()
        name = security.name.upper()


        if len(ticker) <= 5:
            score += 20
            reasons.append(
                "US listed quality ticker"
            )


        for keyword in self.priority_keywords:

            if keyword in name:

                score += 30

                reasons.append(
                    f"Growth sector: {keyword}"
                )

                break


        mega_caps = [
            "NVDA",
            "MSFT",
            "AAPL",
            "GOOGL",
            "AMZN",
            "META",
            "AVGO",
            "TSLA",
        ]


        if ticker in mega_caps:

            score += 50

            reasons.append(
                "Mega growth company"
            )


        return GrowthCandidate(
            ticker=security.ticker,
            name=security.name,
            cik=security.cik,
            growth_score=min(score,100),
            reason=reasons,
        )


    def build(
        self,
        universe: List[MarketSecurity],
    ) -> List[GrowthCandidate]:

        candidates = []


        for security in universe:

            candidate = self.calculate_score(
                security
            )


            if candidate.growth_score >= 40:

                candidates.append(
                    candidate
                )


        candidates.sort(
            key=lambda x:x.growth_score,
            reverse=True,
        )


        return candidates

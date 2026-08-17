from __future__ import annotations

import urllib.request
import json

from dataclasses import dataclass

from ai.research.financial.sec_cache import SECCache
from ai.research.governance.api_governor import APIGovernor



@dataclass
class FinancialMetrics:

    ticker: str

    revenue: float = 0
    net_income: float = 0
    assets: float = 0
    liabilities: float = 0
    cashflow: float = 0

    quality_score: float = 0


    # compatibility with old dict based modules
    def __contains__(self, key):

        return hasattr(
            self,
            key
        )


    def __getitem__(self, key):

        return getattr(
            self,
            key
        )


    def get(
        self,
        key,
        default=None
    ):

        return getattr(
            self,
            key,
            default
        )





class FinancialIntelligenceV2:


    SEC_URL = (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    )



    def __init__(self):

        self.cache = SECCache()

        self.governor = APIGovernor(
            daily_limit=1000
        )

        self.headers = {

            "User-Agent":
            "Trinity-Wealth-Engine research@example.com"

        }





    def fetch(
        self,
        ticker,
        cik
    ):


        facts={}


        try:

            if self.cache.exists(ticker):

                cached = self.cache.load(
                    ticker
                )

                facts = cached.get(
                    "data",
                    {}
                )


            elif self.governor.allowed():


                self.governor.consume()


                url = self.SEC_URL.format(
                    cik=str(cik).zfill(10)
                )


                request = urllib.request.Request(
                    url,
                    headers=self.headers
                )


                with urllib.request.urlopen(
                    request,
                    timeout=5
                ) as response:


                    facts = json.loads(
                        response.read()
                    )


                self.cache.save(
                    ticker,
                    cik,
                    facts
                )


        except Exception as e:

            print(
                ticker,
                "SEC unavailable"
            )



        metrics = FinancialMetrics(
            ticker=ticker
        )


        metrics.quality_score = (
            self.calculate_quality(
                metrics
            )
        )


        return metrics





    def calculate_quality(
        self,
        financial
    ):


        score=0


        if financial.revenue > 0:

            score += 25


        if financial.net_income > 0:

            score += 25


        if financial.cashflow > 0:

            score += 25


        if financial.assets > financial.liabilities:

            score += 25


        return min(
            score,
            100
        )





    def quality_score(
        self,
        financial
    ):

        return self.calculate_quality(
            financial
        )


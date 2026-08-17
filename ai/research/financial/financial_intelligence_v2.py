from __future__ import annotations

import urllib.request
import json

from ai.research.financial.sec_cache import SECCache
from ai.research.governance.api_governor import APIGovernor


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

        if self.cache.exists(ticker):

            return self.cache.load(
                ticker
            )


        if not self.governor.allowed():

            raise RuntimeError(
                "SEC API limit reached"
            )


        url = self.SEC_URL.format(
            cik=str(cik).zfill(10)
        )


        try:

            self.governor.consume()


            request = urllib.request.Request(
                url,
                headers=self.headers
            )


            with urllib.request.urlopen(
                request,
                timeout=10
            ) as response:

                data=json.loads(
                    response.read()
                )


            self.cache.save(
                ticker,
                cik,
                data
            )


            return {
                "data":data
            }


        except Exception:

            return {
                "data":{},
                "error":
                "SEC unavailable"
            }



    def quality_score(
        self,
        facts
    ):

        if not facts:
            return 0


        score=0


        if "facts" in facts:

            score+=50


        return score


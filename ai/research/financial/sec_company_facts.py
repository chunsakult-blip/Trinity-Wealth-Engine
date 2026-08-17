from __future__ import annotations

import json
import urllib.request

from ai.research.financial.sec_cache import (
    SECCache,
)



class SECCompanyFacts:


    URL = (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK"
        "{cik}.json"
    )


    def __init__(self):

        self.cache = SECCache()

        self.headers = {

            "User-Agent":
            "Trinity-Wealth-Engine contact@example.com"

        }



    def fetch(
        self,
        ticker:str,
        cik:str,
    ):


        # cache first

        if self.cache.exists(
            ticker
        ):

            return self.cache.load(
                ticker
            )



        url = self.URL.format(
            cik=str(cik).zfill(10)
        )



        request = urllib.request.Request(
            url,
            headers=self.headers
        )



        with urllib.request.urlopen(
            request
        ) as response:

            data=json.loads(
                response.read()
            )



        self.cache.save(
            ticker,
            cik,
            data
        )


        return data

from __future__ import annotations

from dataclasses import dataclass
import json
import urllib.request


@dataclass
class MarketSecurity:

    ticker: str
    name: str
    cik: str


class SECMarketLoader:


    SEC_URL = (
        "https://www.sec.gov/files/"
        "company_tickers.json"
    )


    def __init__(self):

        self.headers = {
            "User-Agent":
            "Trinity-Wealth-Engine contact@example.com"
        }


    def load(self):

        request = urllib.request.Request(
            self.SEC_URL,
            headers=self.headers,
        )


        with urllib.request.urlopen(request) as response:

            data = json.loads(
                response.read()
            )


        securities=[]


        for item in data.values():

            securities.append(

                MarketSecurity(

                    ticker=item["ticker"],

                    name=item["title"],

                    cik=str(
                        item["cik_str"]
                    ),

                )

            )


        return securities



from __future__ import annotations

import urllib.request
import json

from dataclasses import dataclass

from ai.research.financial.sec_cache import SECCache
from ai.research.governance.api_governor import APIGovernor


@dataclass
class FinancialMetrics:

    ticker: str
    revenue: float
    net_income: float
    assets: float
    liabilities: float
    cashflow: float
    quality_score: float



class FinancialIntelligenceEngine:


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



    def load_facts(
        self,
        ticker: str,
        cik: str,
    ):

        if self.cache.exists(ticker):

            cached = self.cache.load(ticker)

            return cached.get(
                "data",
                {}
            )


        if not self.governor.allowed():

            return {}


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

                data = json.loads(
                    response.read()
                )


            self.cache.save(
                ticker,
                cik,
                data
            )


            return data


        except Exception as e:

            print(
                ticker,
                "SEC unavailable"
            )

            return {}



    def extract_value(
        self,
        facts,
        tag,
    ):

        try:

            usgaap = facts["facts"]["us-gaap"]

            item = usgaap[tag]

            units = item["units"]

            key = list(
                units.keys()
            )[0]


            return units[key][-1]["val"]


        except Exception:

            return 0



    def analyze(
        self,
        ticker: str,
        cik: str,
    ):


        facts = self.load_facts(
            ticker,
            cik
        )


        revenue = self.extract_value(
            facts,
            "Revenues"
        )


        income = self.extract_value(
            facts,
            "NetIncomeLoss"
        )


        assets = self.extract_value(
            facts,
            "Assets"
        )


        liabilities = self.extract_value(
            facts,
            "Liabilities"
        )


        cashflow = self.extract_value(
            facts,
            "NetCashProvidedByUsedInOperatingActivities"
        )



        score = 0


        if revenue > 0:
            score += 20


        if income > 0:
            score += 25


        if cashflow > 0:
            score += 25


        if assets > liabilities:
            score += 30



        return FinancialMetrics(

            ticker=ticker,

            revenue=revenue,

            net_income=income,

            assets=assets,

            liabilities=liabilities,

            cashflow=cashflow,

            quality_score=min(
                score,
                100
            )

        )

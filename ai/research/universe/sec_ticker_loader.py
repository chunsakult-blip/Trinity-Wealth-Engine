from __future__ import annotations

import json
from pathlib import Path

from dataclasses import dataclass


@dataclass
class Company:
    ticker: str
    name: str
    cik: str


class SECTickerLoader:


    def __init__(self):
        self.file = Path(
            ".data/sec/company_tickers.json"
        )


    def load(self):

        if not self.file.exists():
            raise FileNotFoundError(
                "SEC ticker file missing"
            )


        with open(
            self.file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)


        companies = []


        for item in data.values():

            companies.append(
                Company(
                    ticker=item["ticker"],
                    name=item["title"],
                    cik=str(
                        item["cik_str"]
                    ),
                )
            )


        return companies


    def search(
        self,
        ticker: str
    ):

        companies = self.load()

        ticker = ticker.upper()


        for company in companies:

            if company.ticker == ticker:
                return company


        return None

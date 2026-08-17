from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Security:
    ticker: str
    name: str
    cik: str
    exchange: str


class USMarketUniverse:

    def __init__(self):
        self.securities: List[Security] = []


    def add(
        self,
        ticker: str,
        name: str,
        cik: str,
        exchange: str,
    ):
        self.securities.append(
            Security(
                ticker=ticker,
                name=name,
                cik=cik,
                exchange=exchange,
            )
        )


    def load_seed(self):

        self.add(
            ticker="AAPL",
            name="Apple Inc.",
            cik="320193",
            exchange="NASDAQ",
        )

        self.add(
            ticker="MSFT",
            name="Microsoft Corporation",
            cik="789019",
            exchange="NASDAQ",
        )

        self.add(
            ticker="NVDA",
            name="NVIDIA Corporation",
            cik="1045810",
            exchange="NASDAQ",
        )

        self.add(
            ticker="GOOGL",
            name="Alphabet Inc.",
            cik="1652044",
            exchange="NASDAQ",
        )

        return self.securities


    def all(self):

        return self.securities

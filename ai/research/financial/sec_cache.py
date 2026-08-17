from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime



@dataclass
class SECCacheRecord:

    ticker: str
    cik: str
    fetched_at: str
    data: dict



class SECCache:


    def __init__(
        self,
        cache_dir="data/sec_cache"
    ):

        self.cache_dir = Path(
            cache_dir
        )

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True
        )



    def path(
        self,
        ticker:str
    ):

        return (
            self.cache_dir
            /
            f"{ticker}.json"
        )



    def exists(
        self,
        ticker:str
    ):

        return self.path(
            ticker
        ).exists()



    def save(
        self,
        ticker:str,
        cik:str,
        data:dict,
    ):


        record = {

            "ticker": ticker,

            "cik": cik,

            "fetched_at":
                datetime.now()
                .isoformat(),

            "data": data,

        }


        with open(
            self.path(ticker),
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                record,
                f,
                indent=2
            )



    def load(
        self,
        ticker:str
    ):


        with open(
            self.path(ticker),
            encoding="utf-8"
        ) as f:

            return json.load(f)


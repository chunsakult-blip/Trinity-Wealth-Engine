from __future__ import annotations

from typing import List


class UniverseDeduplicator:


    OTC_SUFFIX = [
        "F",
        "Y",
        "W",
    ]


    def clean(
        self,
        candidates: List,
    ):


        result=[]

        seen=set()


        for item in candidates:

            ticker=item.ticker.upper()


            # remove duplicates
            if ticker in seen:
                continue


            seen.add(ticker)


            # remove obvious OTC
            if len(ticker)>5:
                continue


            result.append(item)


        return result

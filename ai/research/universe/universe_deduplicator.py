from __future__ import annotations

from typing import List


class UniverseDeduplicator:


    def clean(
        self,
        candidates: List,
    ):

        result = []

        seen = set()


        for item in candidates:

            ticker = item.ticker.upper()


            # duplicate protection
            if ticker in seen:
                continue


            seen.add(ticker)


            # remove OTC / strange symbols
            if len(ticker) > 5:
                continue


            # remove obvious suffix listings
            if ticker.endswith(
                ("F", "Y", "W")
            ):
                continue


            result.append(item)


        return result

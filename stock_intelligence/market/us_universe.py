from __future__ import annotations

import io
import urllib.request
from dataclasses import dataclass


NASDAQ_LISTED_URL = (
    "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
)

OTHER_LISTED_URL = (
    "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"
)


@dataclass(frozen=True)
class UniverseStock:
    ticker: str
    exchange: str
    security_name: str
    etf: bool = False


def _download(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Trinity-Wealth-Engine/1.0 "
                "(research; contact@example.com)"
            )
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        return response.read().decode(
            "utf-8",
            errors="replace",
        )


def _parse_pipe_table(
    text: str,
) -> list[dict[str, str]]:

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return []

    header = None
    result = []

    for line in lines:

        if line.startswith("File Creation Time"):
            continue

        parts = line.split("|")

        if header is None:
            header = parts
            continue

        if parts == header:
            continue

        if len(parts) != len(header):
            continue

        result.append(
            dict(
                zip(
                    header,
                    parts,
                )
            )
        )

    return result


def _normalize_ticker(
    ticker: str,
) -> str:

    ticker = ticker.strip().upper()

    # Yahoo Finance convention.
    # BRK/A -> BRK-A
    # BF/B  -> BF-B
    ticker = ticker.replace("/", "-")

    return ticker


def discover_us_equities() -> list[UniverseStock]:

    result: dict[str, UniverseStock] = {}

    # --------------------------------------------------------------
    # NASDAQ
    # --------------------------------------------------------------

    try:

        rows = _parse_pipe_table(
            _download(
                NASDAQ_LISTED_URL
            )
        )

        for row in rows:

            ticker = _normalize_ticker(
                row.get("Symbol", "")
            )

            security_name = row.get(
                "Security Name",
                "",
            )

            etf = (
                row.get("ETF", "").upper()
                == "Y"
            )

            test_issue = (
                row.get(
                    "Test Issue",
                    "",
                ).upper()
                == "Y"
            )

            if (
                not ticker
                or test_issue
                or etf
            ):
                continue

            result[ticker] = UniverseStock(
                ticker=ticker,
                exchange="NASDAQ",
                security_name=security_name,
                etf=False,
            )

    except Exception as exc:

        print(
            "WARNING: NASDAQ universe download failed:",
            type(exc).__name__,
            exc,
        )

    # --------------------------------------------------------------
    # NYSE / AMEX / OTHER
    # --------------------------------------------------------------

    try:

        rows = _parse_pipe_table(
            _download(
                OTHER_LISTED_URL
            )
        )

        for row in rows:

            ticker = _normalize_ticker(
                row.get(
                    "ACT Symbol",
                    "",
                )
            )

            security_name = row.get(
                "Security Name",
                "",
            )

            etf = (
                row.get("ETF", "").upper()
                == "Y"
            )

            test_issue = (
                row.get(
                    "Test Issue",
                    "",
                ).upper()
                == "Y"
            )

            if (
                not ticker
                or test_issue
                or etf
            ):
                continue

            exchange_code = row.get(
                "Exchange",
                "",
            ).upper()

            exchange = {
                "N": "NYSE",
                "A": "NYSE MKT",
                "P": "NYSE ARCA",
                "Z": "BATS",
                "V": "IEX",
            }.get(
                exchange_code,
                "OTHER",
            )

            result[ticker] = UniverseStock(
                ticker=ticker,
                exchange=exchange,
                security_name=security_name,
                etf=False,
            )

    except Exception as exc:

        print(
            "WARNING: OTHER universe download failed:",
            type(exc).__name__,
            exc,
        )

    return sorted(
        result.values(),
        key=lambda x: x.ticker,
    )


def build_large_us_universe() -> list[str]:

    stocks = discover_us_equities()

    return [
        stock.ticker
        for stock in stocks
    ]


if __name__ == "__main__":

    stocks = discover_us_equities()

    print("")
    print("=" * 72)
    print("NICK V3 — LARGE US EQUITY UNIVERSE")
    print("=" * 72)
    print("")
    print("Total equities:", len(stocks))
    print("")

    for stock in stocks[:100]:
        print(
            f"{stock.ticker:<10}"
            f"{stock.exchange:<12}"
            f"{stock.security_name}"
        )

    print("")
    print(
        "Showing first 100 of",
        len(stocks),
    )

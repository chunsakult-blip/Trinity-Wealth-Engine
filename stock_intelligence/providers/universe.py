from __future__ import annotations

from typing import Iterable


# High-quality initial US equity universe.
# This is intentionally deterministic and dependency-light.
#
# The universe can later be expanded to the full US market
# through additional index / exchange discovery providers.

CORE_US_UNIVERSE: tuple[str, ...] = (

    # Mega-cap technology
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "GOOG",
    "AVGO",
    "ORCL",
    "ADBE",
    "CRM",
    "CSCO",
    "AMD",
    "INTC",
    "QCOM",
    "TXN",
    "AMAT",
    "MU",
    "LRCX",
    "KLAC",
    "ADI",

    # Semiconductors / AI infrastructure
    "ARM",
    "MRVL",
    "TSM",
    "ASML",
    "SMCI",
    "ANET",
    "DELL",
    "HPE",

    # Consumer
    "TSLA",
    "NFLX",
    "COST",
    "WMT",
    "HD",
    "LOW",
    "MCD",
    "SBUX",
    "NKE",
    "TJX",
    "TGT",
    "BKNG",
    "ABNB",

    # Financial
    "BRK-B",
    "JPM",
    "V",
    "MA",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "BLK",
    "SCHW",
    "AXP",
    "C",
    "USB",

    # Healthcare
    "LLY",
    "UNH",
    "JNJ",
    "MRK",
    "ABBV",
    "PFE",
    "TMO",
    "ABT",
    "DHR",
    "ISRG",
    "AMGN",
    "GILD",
    "VRTX",

    # Industrial
    "CAT",
    "DE",
    "GE",
    "HON",
    "RTX",
    "BA",
    "UPS",
    "UNP",
    "LMT",
    "ETN",
    "PH",
    "EMR",

    # Energy
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "SLB",
    "OXY",

    # Communication
    "T",
    "VZ",
    "TMUS",
    "CMCSA",

    # Software / cybersecurity
    "NOW",
    "PANW",
    "CRWD",
    "SNOW",
    "PLTR",
    "DDOG",
    "FTNT",
    "INTU",
    "PYPL",
    "SQ",

    # Consumer / restaurants
    "KO",
    "PEP",
    "PM",
    "MO",
    "MDLZ",
    "CL",
    "PG",

    # REIT / infrastructure
    "PLD",
    "AMT",
    "EQIX",
    "CCI",

)


def build_us_universe() -> list[str]:

    seen: set[str] = set()
    result: list[str] = []

    for ticker in CORE_US_UNIVERSE:

        ticker = ticker.upper().strip()

        if ticker and ticker not in seen:

            seen.add(ticker)
            result.append(ticker)

    return result


def normalize_tickers(
    tickers: Iterable[str],
) -> list[str]:

    seen: set[str] = set()
    result: list[str] = []

    for ticker in tickers:

        ticker = str(ticker).upper().strip()

        if ticker and ticker not in seen:

            seen.add(ticker)
            result.append(ticker)

    return result


if __name__ == "__main__":

    universe = build_us_universe()

    print("US UNIVERSE")
    print("=" * 60)
    print("Count:", len(universe))

    for ticker in universe:
        print(ticker)

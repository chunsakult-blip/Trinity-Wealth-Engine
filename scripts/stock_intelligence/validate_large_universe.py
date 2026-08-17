from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from stock_intelligence.market.us_universe import (
    discover_us_equities,
)

from stock_intelligence.warehouse.v3_warehouse import (
    V3Warehouse,
)


def main():

    print("")
    print("=" * 78)
    print("NICK V3 — LARGE US MARKET DISCOVERY TEST")
    print("=" * 78)
    print("")

    stocks = discover_us_equities()

    print(
        "Discovered equities:",
        len(stocks),
    )

    print("")

    if not stocks:

        print(
            "ERROR: No US equities discovered."
        )

        raise SystemExit(1)

    print(
        "First 30:"
    )

    print(
        "-" * 78
    )

    for stock in stocks[:30]:

        print(
            f"{stock.ticker:<10}"
            f"{stock.exchange:<12}"
            f"{stock.security_name[:50]}"
        )

    print("")
    print(
        "Last 10:"
    )

    print(
        "-" * 78
    )

    for stock in stocks[-10:]:

        print(
            f"{stock.ticker:<10}"
            f"{stock.exchange:<12}"
            f"{stock.security_name[:50]}"
        )

    db = V3Warehouse()

    print("")
    print(
        "Warehouse:",
        db.path,
    )

    print("")
    print(
        "Warehouse tables:"
    )

    for key, value in db.counts().items():

        print(
            f"{key:<25}: {value}"
        )

    print("")
    print("=" * 78)
    print("DISCOVERY TEST COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()

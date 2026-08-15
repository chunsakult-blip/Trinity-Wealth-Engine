from __future__ import annotations

import argparse
import time

from stock_intelligence.providers.universe import build_us_universe
from stock_intelligence.providers.yfinance_provider import fetch_stock
from stock_intelligence.screening.nick_screen import screen_stock
from stock_intelligence.storage.database import StockDatabase


def run(
    limit: int | None = None,
    sleep_seconds: float = 0.20,
):

    db = StockDatabase()

    print("")
    print("=" * 72)
    print("ATLAS / TRINITY STOCK INTELLIGENCE PIPELINE")
    print("=" * 72)

    print("")
    print("[1/4] BUILD US UNIVERSE")

    tickers = build_us_universe()

    if limit is not None:
        tickers = tickers[:limit]

    db.save_universe(
        tickers,
        source="core_us_universe",
    )

    print(f"Universe: {len(tickers)}")

    print("")
    print("[2/4] INGEST + SCREEN")

    run_id = db.start_run(len(tickers))

    success = 0
    failed = 0

    for index, ticker in enumerate(
        tickers,
        start=1,
    ):

        print(
            f"[{index:03d}/{len(tickers):03d}] "
            f"{ticker:<8}",
            end=" ",
            flush=True,
        )

        try:

            stock = fetch_stock(ticker)

            stock = screen_stock(stock)

            db.save_stock(stock)

            print(
                f"{stock.tier:<8} "
                f"score={stock.composite_score:6.2f} "
                f"data={stock.data_completeness:.0%}"
            )

            success += 1

        except Exception as exc:

            failed += 1

            print(
                f"ERROR "
                f"{type(exc).__name__}: {exc}"
            )

        if sleep_seconds > 0:

            time.sleep(
                sleep_seconds
            )

    db.finish_run(
        run_id,
        success,
        failed,
    )

    print("")
    print("[3/4] DATABASE SUMMARY")

    print(
        "Universe:",
        db.count_universe(),
    )

    print(
        "Stocks:",
        db.count_stocks(),
    )

    print(
        "Tiers:",
        db.tier_counts(),
    )

    print("")
    print("[4/4] TOP CANDIDATES")

    rows = db.top_stocks(30)

    if not rows:

        print("No stock records.")

    else:

        for row in rows:

            print(
                f"{row['ticker']:<8} "
                f"{row['tier']:<8} "
                f"{row['decision']:<15} "
                f"score={row['composite_score']:6.2f} "
                f"data={row['data_completeness']:.0%}"
            )

    print("")
    print("=" * 72)
    print("PIPELINE COMPLETE")
    print("=" * 72)

    print(
        f"SUCCESS: {success}"
    )

    print(
        f"FAILED : {failed}"
    )

    print("=" * 72)

    return 0 if success > 0 else 1


def main():

    parser = argparse.ArgumentParser(
        description="ATLAS / Trinity Stock Intelligence",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=0.20,
    )

    args = parser.parse_args()

    raise SystemExit(
        run(
            limit=args.limit,
            sleep_seconds=args.sleep,
        )
    )


if __name__ == "__main__":
    main()

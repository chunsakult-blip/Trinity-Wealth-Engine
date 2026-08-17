from __future__ import annotations

import sys
from pathlib import Path

# ------------------------------------------------------------
# PROJECT ROOT
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ------------------------------------------------------------
# CORE IMPORTS
# ------------------------------------------------------------

from stock_intelligence.providers.yfinance_provider import fetch_stock
from stock_intelligence.screening.nick_screen import screen_stock


# ------------------------------------------------------------
# TEST UNIVERSE
# ------------------------------------------------------------

TICKERS = [
    "NVDA",
    "MSFT",
    "AAPL",
    "GOOGL",
    "AMZN",
    "META",
    "AVGO",
    "TSLA",
    "JPM",
    "LLY",
]


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():

    print("")
    print("=" * 110)
    print("NICK ENGINE V2 — 10 STOCK VALIDATION")
    print("=" * 110)

    print("")

    print(
        f"{'TICKER':<8}"
        f"{'QUALITY':>10}"
        f"{'GROWTH':>10}"
        f"{'HEALTH':>10}"
        f"{'VALUE':>10}"
        f"{'MOMENT':>10}"
        f"{'TOTAL':>10}"
        f"{'DATA':>8}"
        f"{'TIER':>10}"
        f"{'DECISION':>18}"
    )

    print("-" * 110)

    results = []

    for ticker in TICKERS:

        try:

            stock = fetch_stock(ticker)

            stock = screen_stock(stock)

            results.append(stock)

            print(
                f"{stock.ticker:<8}"
                f"{stock.quality_score:>10.2f}"
                f"{stock.growth_score:>10.2f}"
                f"{stock.financial_health_score:>10.2f}"
                f"{stock.valuation_score:>10.2f}"
                f"{stock.momentum_score:>10.2f}"
                f"{stock.composite_score:>10.2f}"
                f"{stock.data_completeness:>7.0%}"
                f"{stock.tier:>10}"
                f"{stock.decision:>18}"
            )

        except Exception as exc:

            print(
                f"{ticker:<8}"
                f"ERROR: {type(exc).__name__}: {exc}"
            )

    print("")
    print("=" * 110)

    # --------------------------------------------------------
    # RANKING
    # --------------------------------------------------------

    print("")
    print("RANKING")
    print("-" * 110)

    ranked = sorted(
        results,
        key=lambda x: x.composite_score,
        reverse=True,
    )

    for index, stock in enumerate(
        ranked,
        start=1,
    ):

        print(
            f"{index:02d}. "
            f"{stock.ticker:<8} "
            f"{stock.composite_score:6.2f} "
            f"{stock.tier:<8} "
            f"{stock.decision:<18} "
            f"Quality={stock.business_quality:<10} "
            f"Risk={stock.risk_flags or 'NONE'}"
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("")
    print("=" * 110)
    print("VALIDATION SUMMARY")
    print("=" * 110)

    print(
        f"Requested : {len(TICKERS)}"
    )

    print(
        f"Success   : {len(results)}"
    )

    print(
        f"Failed    : {len(TICKERS) - len(results)}"
    )

    tier1 = sum(
        1
        for stock in results
        if stock.tier == "TIER_1"
    )

    tier2 = sum(
        1
        for stock in results
        if stock.tier == "TIER_2"
    )

    tier3 = sum(
        1
        for stock in results
        if stock.tier == "TIER_3"
    )

    print(
        f"TIER_1    : {tier1}"
    )

    print(
        f"TIER_2    : {tier2}"
    )

    print(
        f"TIER_3    : {tier3}"
    )

    print("")

    if ranked:

        print(
            f"TOP STOCK : {ranked[0].ticker}"
        )

        print(
            f"TOP SCORE : {ranked[0].composite_score:.2f}"
        )

        print(
            f"TOP TIER  : {ranked[0].tier}"
        )

        print(
            f"TOP DECISION: {ranked[0].decision}"
        )

    print("")
    print("=" * 110)
    print("10-STOCK VALIDATION COMPLETE")
    print("=" * 110)


if __name__ == "__main__":
    main()

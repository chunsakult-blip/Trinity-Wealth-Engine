from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_intelligence.providers.yfinance_provider import fetch_stock
from stock_intelligence.screening.nick_screen import screen_stock


def fmt(value):

    if value is None:
        return "N/A"

    if isinstance(value, float):
        return f"{value:.4f}"

    return str(value)


def pct(value):

    if value is None:
        return "N/A"

    return f"{value:.2%}"


def main():

    import argparse

    parser = argparse.ArgumentParser(
        description="Nick Stock Intelligence Inspector v2"
    )

    parser.add_argument(
        "ticker"
    )

    args = parser.parse_args()

    ticker = args.ticker.upper().strip()

    stock = fetch_stock(ticker)

    stock = screen_stock(stock)

    print("")
    print("=" * 78)
    print(f"NICK STOCK INTELLIGENCE V2 — {ticker}")
    print("=" * 78)

    print("")
    print("IDENTITY")
    print("-" * 78)
    print(f"Ticker          : {stock.ticker}")
    print(f"Company         : {stock.company_name}")
    print(f"Exchange        : {stock.exchange}")
    print(f"Sector          : {stock.sector}")
    print(f"Industry        : {stock.industry}")

    print("")
    print("MARKET")
    print("-" * 78)
    print(f"Price           : {fmt(stock.price)}")
    print(f"Market Cap      : {fmt(stock.market_cap)}")
    print(f"52W Low         : {fmt(stock.fifty_two_week_low)}")
    print(f"52W High        : {fmt(stock.fifty_two_week_high)}")
    print(f"Beta            : {fmt(stock.beta)}")

    print("")
    print("FUNDAMENTALS")
    print("-" * 78)
    print(f"Revenue         : {fmt(stock.revenue)}")
    print(f"Revenue Growth  : {pct(stock.revenue_growth)}")
    print(f"EPS             : {fmt(stock.eps)}")
    print(f"EPS Growth      : {pct(stock.eps_growth)}")
    print(f"FCF             : {fmt(stock.free_cash_flow)}")
    print(f"FCF Yield       : {pct(stock.fcf_yield)}")

    print("")
    print("RETURNS")
    print("-" * 78)
    print(f"ROE             : {pct(stock.roe)}")
    print(f"ROA             : {pct(stock.roa)}")
    print(f"ROIC            : {pct(stock.roic)}")

    print("")
    print("BALANCE SHEET")
    print("-" * 78)
    print(f"Cash            : {fmt(stock.total_cash)}")
    print(f"Debt            : {fmt(stock.total_debt)}")
    print(f"Net Debt        : {fmt(stock.net_debt)}")
    print(f"Debt / Equity   : {fmt(stock.debt_to_equity)}")
    print(f"Current Ratio   : {fmt(stock.current_ratio)}")

    print("")
    print("VALUATION")
    print("-" * 78)
    print(f"PE              : {fmt(stock.pe)}")
    print(f"Forward PE      : {fmt(stock.forward_pe)}")
    print(f"PEG             : {fmt(stock.peg)}")
    print(f"P/S             : {fmt(stock.price_to_sales)}")
    print(f"P/B             : {fmt(stock.price_to_book)}")
    print(f"EV / EBITDA     : {fmt(stock.ev_to_ebitda)}")

    print("")
    print("NICK SCORES")
    print("-" * 78)
    print(f"Quality         : {stock.quality_score:7.2f}")
    print(f"Growth          : {stock.growth_score:7.2f}")
    print(f"Health          : {stock.financial_health_score:7.2f}")
    print(f"Valuation       : {stock.valuation_score:7.2f}")
    print(f"Momentum        : {stock.momentum_score:7.2f}")
    print(f"Composite       : {stock.composite_score:7.2f}")

    print("")
    print("DATA QUALITY")
    print("-" * 78)
    print(f"Completeness    : {stock.data_completeness:.0%}")
    print(f"Confidence      : {stock.data_confidence:.0%}")

    print("")
    print("RISK")
    print("-" * 78)
    print(f"Risk Flags      : {stock.risk_flags or 'NONE'}")
    print(f"Hard Failures   : {stock.hard_failures or 'NONE'}")

    print("")
    print("NICK VERDICT")
    print("-" * 78)
    print(f"Business Quality: {stock.business_quality}")
    print(f"Tier            : {stock.tier}")
    print(f"Decision        : {stock.decision}")

    print("")
    print("=" * 78)
    print("INSPECTION COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()

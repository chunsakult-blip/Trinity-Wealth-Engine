from __future__ import annotations

import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from stock_intelligence.market.us_universe import (
    discover_us_equities,
)

from stock_intelligence.warehouse.v3_warehouse import (
    V3Warehouse,
)


# ======================================================================
# CONFIGURATION
# ======================================================================

SOURCE = "yfinance"

DB_PATH = "data/stock_intelligence_v3.sqlite"

REQUEST_DELAY = 0.75

MAX_RETRIES = 3

CHECKPOINT_EVERY = 25


# ======================================================================
# HELPERS
# ======================================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_number(value):
    try:
        if value is None:
            return None

        value = float(value)

        if math.isnan(value):
            return None

        if math.isinf(value):
            return None

        return value

    except Exception:
        return None


def safe_div(numerator, denominator):

    numerator = clean_number(numerator)
    denominator = clean_number(denominator)

    if numerator is None:
        return None

    if denominator is None:
        return None

    if denominator == 0:
        return None

    return numerator / denominator


def dataframe_row_series(dataframe, name):

    if dataframe is None:
        return []

    try:

        if name not in dataframe.index:
            return []

        row = dataframe.loc[name]

        result = []

        for index, value in row.items():

            value = clean_number(value)

            if value is None:
                continue

            result.append(
                (
                    str(index),
                    value,
                )
            )

        return result

    except Exception:
        return []


def first_row_value(dataframe, names):

    if dataframe is None:
        return None

    for name in names:

        try:

            if name not in dataframe.index:
                continue

            row = dataframe.loc[name]

            if hasattr(row, "dropna"):
                row = row.dropna()

            if len(row) == 0:
                continue

            value = clean_number(row.iloc[0])

            if value is not None:
                return value

        except Exception:
            continue

    return None


def calculate_growth(series):

    if not series:
        return {}

    # yfinance financial statements normally return newest -> oldest.
    # Sort chronologically before calculating YoY growth.

    ordered = sorted(
        series,
        key=lambda item: item[0],
    )

    growth = {}

    for index in range(1, len(ordered)):

        previous_period, previous_value = ordered[index - 1]

        current_period, current_value = ordered[index]

        if previous_value == 0:
            growth[current_period] = None
            continue

        growth[current_period] = (
            current_value
            / previous_value
            - 1.0
        )

    return growth


def period_year(period_end):

    try:
        return int(
            str(period_end)[:4]
        )

    except Exception:
        return None


# ======================================================================
# SECURITY
# ======================================================================

def insert_security(
    db,
    stock,
):

    with db.connect() as conn:

        conn.execute(
            """
            INSERT INTO securities (
                ticker,
                exchange,
                security_name,
                security_type,
                source,
                fetched_at
            )

            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(ticker)
            DO UPDATE SET

                exchange = excluded.exchange,

                security_name = excluded.security_name,

                security_type = excluded.security_type,

                source = excluded.source,

                fetched_at = excluded.fetched_at
            """,
            (
                stock.ticker,
                stock.exchange,
                stock.security_name,
                "COMMON_STOCK",
                SOURCE,
                now_iso(),
            ),
        )

        conn.commit()


# ======================================================================
# FUNDAMENTALS
# ======================================================================

def insert_fundamentals(
    db,
    ticker,
    income,
    balance,
    cashflow,
):

    revenue_series = dataframe_row_series(
        income,
        "Total Revenue",
    )

    gross_profit_series = dataframe_row_series(
        income,
        "Gross Profit",
    )

    operating_income_series = dataframe_row_series(
        income,
        "Operating Income",
    )

    net_income_series = dataframe_row_series(
        income,
        "Net Income",
    )

    eps_series = dataframe_row_series(
        income,
        "Diluted EPS",
    )

    fcf_series = dataframe_row_series(
        cashflow,
        "Free Cash Flow",
    )

    ocf_series = dataframe_row_series(
        cashflow,
        "Operating Cash Flow",
    )

    capex_series = dataframe_row_series(
        cashflow,
        "Capital Expenditure",
    )

    cash = first_row_value(
        balance,
        [
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Cash Equivalents",
        ],
    )

    debt = first_row_value(
        balance,
        [
            "Total Debt",
        ],
    )

    assets = first_row_value(
        balance,
        [
            "Total Assets",
        ],
    )

    equity = first_row_value(
        balance,
        [
            "Stockholders Equity",
            "Total Equity Gross Minority Interest",
        ],
    )

    shares = first_row_value(
        balance,
        [
            "Ordinary Shares Number",
            "Share Issued",
        ],
    )

    gross_profit_map = dict(
        gross_profit_series
    )

    operating_income_map = dict(
        operating_income_series
    )

    net_income_map = dict(
        net_income_series
    )

    eps_map = dict(
        eps_series
    )

    fcf_map = dict(
        fcf_series
    )

    ocf_map = dict(
        ocf_series
    )

    capex_map = dict(
        capex_series
    )

    revenue_growth_map = calculate_growth(
        revenue_series
    )

    eps_growth_map = calculate_growth(
        eps_series
    )

    inserted = 0

    for period_end, revenue in revenue_series:

        gross_profit = gross_profit_map.get(
            period_end
        )

        operating_income = operating_income_map.get(
            period_end
        )

        net_income = net_income_map.get(
            period_end
        )

        eps = eps_map.get(
            period_end
        )

        fcf = fcf_map.get(
            period_end
        )

        ocf = ocf_map.get(
            period_end
        )

        capex = capex_map.get(
            period_end
        )

        revenue_growth = revenue_growth_map.get(
            period_end
        )

        eps_growth = eps_growth_map.get(
            period_end
        )

        gross_margin = safe_div(
            gross_profit,
            revenue,
        )

        operating_margin = safe_div(
            operating_income,
            revenue,
        )

        profit_margin = safe_div(
            net_income,
            revenue,
        )

        roe = safe_div(
            net_income,
            equity,
        )

        roa = safe_div(
            net_income,
            assets,
        )

        net_debt = None

        if (
            debt is not None
            and cash is not None
        ):
            net_debt = debt - cash

        debt_to_equity = safe_div(
            debt,
            equity,
        )

        with db.connect() as conn:

            conn.execute(
                """
                INSERT OR REPLACE INTO fundamentals (

                    ticker,
                    period_end,
                    fiscal_year,

                    revenue,
                    revenue_growth,

                    eps,
                    eps_growth,

                    gross_profit,
                    operating_income,
                    net_income,

                    free_cash_flow,
                    operating_cash_flow,
                    capital_expenditure,

                    total_cash,
                    total_debt,
                    net_debt,

                    total_assets,
                    total_equity,

                    shares_outstanding,

                    roe,
                    roa,
                    roic,

                    gross_margin,
                    operating_margin,
                    profit_margin,

                    current_ratio,
                    debt_to_equity,

                    source,
                    fetched_at
                )

                VALUES (
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?
                )
                """,
                (
                    ticker,
                    period_end,
                    period_year(period_end),

                    revenue,
                    revenue_growth,

                    eps,
                    eps_growth,

                    gross_profit,
                    operating_income,
                    net_income,

                    fcf,
                    ocf,
                    capex,

                    cash,
                    debt,
                    net_debt,

                    assets,
                    equity,

                    shares,

                    roe,
                    roa,
                    None,

                    gross_margin,
                    operating_margin,
                    profit_margin,

                    None,
                    debt_to_equity,

                    SOURCE,
                    now_iso(),
                ),
            )

            conn.commit()

        inserted += 1

    return inserted


# ======================================================================
# MARKET HISTORY
# ======================================================================

def ingest_market_snapshot(
    db,
    ticker,
):

    try:

        yf_ticker = yf.Ticker(
            ticker
        )

        history = yf_ticker.history(
            period="5d",
            auto_adjust=False,
        )

        if history is None:
            return False

        if history.empty:
            return False

        with db.connect() as conn:

            for index, row in history.iterrows():

                date = index.strftime(
                    "%Y-%m-%d"
                )

                conn.execute(
                    """
                    INSERT OR REPLACE INTO market_history (

                        ticker,
                        date,

                        open,
                        high,
                        low,
                        close,
                        volume,

                        market_cap,

                        source
                    )

                    VALUES (
                        ?, ?,
                        ?, ?, ?, ?, ?,
                        ?,
                        ?
                    )
                    """,
                    (
                        ticker,
                        date,

                        clean_number(
                            row.get("Open")
                        ),

                        clean_number(
                            row.get("High")
                        ),

                        clean_number(
                            row.get("Low")
                        ),

                        clean_number(
                            row.get("Close")
                        ),

                        clean_number(
                            row.get("Volume")
                        ),

                        None,

                        SOURCE,
                    ),
                )

            conn.commit()

        return True

    except Exception:
        return False


# ======================================================================
# SINGLE STOCK
# ======================================================================

def ingest_stock(
    db,
    stock,
):

    ticker = stock.ticker

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            yf_ticker = yf.Ticker(
                ticker
            )

            income = yf_ticker.financials

            balance = yf_ticker.balance_sheet

            cashflow = yf_ticker.cashflow

            if (
                income is None
                or income.empty
            ):

                raise RuntimeError(
                    "No income statement"
                )

            fundamentals_count = (
                insert_fundamentals(
                    db,
                    ticker,
                    income,
                    balance,
                    cashflow,
                )
            )

            market_ok = (
                ingest_market_snapshot(
                    db,
                    ticker,
                )
            )

            insert_security(
                db,
                stock,
            )

            return {
                "success": True,
                "ticker": ticker,
                "fundamentals": fundamentals_count,
                "market": market_ok,
                "error": None,
            }

        except Exception as exc:

            last_error = (
                f"{type(exc).__name__}: {exc}"
            )

            if attempt < MAX_RETRIES:

                time.sleep(
                    attempt * 2
                )

    return {
        "success": False,
        "ticker": ticker,
        "fundamentals": 0,
        "market": False,
        "error": last_error,
    }


# ======================================================================
# EXISTING DATA
# ======================================================================

def existing_tickers(
    db,
):

    with db.connect() as conn:

        rows = conn.execute(
            """
            SELECT DISTINCT ticker
            FROM fundamentals
            """
        ).fetchall()

    return {
        row["ticker"]
        for row in rows
    }


# ======================================================================
# MAIN
# ======================================================================

def main():

    print("")
    print("=" * 90)
    print("NICK V3 — LARGE SCALE FUNDAMENTAL INGESTION")
    print("=" * 90)
    print("")

    db = V3Warehouse(
        DB_PATH
    )

    stocks = discover_us_equities()

    print(
        f"Universe discovered : {len(stocks):,}"
    )

    completed = existing_tickers(
        db
    )

    print(
        f"Already processed    : {len(completed):,}"
    )

    pending = [
        stock
        for stock in stocks
        if stock.ticker not in completed
    ]

    print(
        f"Remaining            : {len(pending):,}"
    )

    print("")

    if not pending:

        print(
            "Nothing to ingest."
        )

        return

    started_at = now_iso()

    success = 0

    failed = 0

    with db.connect() as conn:

        cursor = conn.execute(
            """
            INSERT INTO universe_runs (
                started_at,
                source,
                total,
                succeeded,
                failed
            )

            VALUES (?, ?, ?, ?, ?)
            """,
            (
                started_at,
                SOURCE,
                len(pending),
                0,
                0,
            ),
        )

        run_id = cursor.lastrowid

        conn.commit()

    for index, stock in enumerate(
        pending,
        start=1,
    ):

        result = ingest_stock(
            db,
            stock,
        )

        if result["success"]:

            success += 1

            print(
                f"[{index:04d}/{len(pending):04d}] "
                f"{stock.ticker:<8} "
                f"OK "
                f"fundamentals={result['fundamentals']} "
                f"market={'OK' if result['market'] else 'FAIL'}"
            )

        else:

            failed += 1

            print(
                f"[{index:04d}/{len(pending):04d}] "
                f"{stock.ticker:<8} "
                f"FAILED "
                f"{result['error']}"
            )

        if index % CHECKPOINT_EVERY == 0:

            with db.connect() as conn:

                conn.execute(
                    """
                    UPDATE universe_runs

                    SET succeeded = ?,
                        failed = ?

                    WHERE id = ?
                    """,
                    (
                        success,
                        failed,
                        run_id,
                    ),
                )

                conn.commit()

            print("")
            print(
                f"CHECKPOINT "
                f"processed={index:,} "
                f"success={success:,} "
                f"failed={failed:,}"
            )
            print("")

        time.sleep(
            REQUEST_DELAY
        )

    completed_at = now_iso()

    with db.connect() as conn:

        conn.execute(
            """
            UPDATE universe_runs

            SET completed_at = ?,
                succeeded = ?,
                failed = ?

            WHERE id = ?
            """,
            (
                completed_at,
                success,
                failed,
                run_id,
            ),
        )

        conn.commit()

    print("")
    print("=" * 90)
    print("INGESTION COMPLETE")
    print("=" * 90)

    print(
        f"Requested : {len(pending):,}"
    )

    print(
        f"Success   : {success:,}"
    )

    print(
        f"Failed    : {failed:,}"
    )

    print("")

    for key, value in db.counts().items():

        print(
            f"{key:<25}: {value:,}"
        )

    print("")
    print("=" * 90)


if __name__ == "__main__":
    main()

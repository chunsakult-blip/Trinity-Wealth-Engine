from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from stock_intelligence.models import StockRecord


def _num(value: Any) -> float | None:

    if value is None:
        return None

    try:
        value = float(value)

        if math.isfinite(value):
            return value

    except (TypeError, ValueError):
        pass

    return None


def _safe(
    info: dict[str, Any],
    *keys: str,
) -> Any:

    for key in keys:

        value = info.get(key)

        if value is not None:
            return value

    return None


def _statement_value(
    statement,
    names: list[str],
) -> float | None:

    if statement is None:
        return None

    try:

        for name in names:

            if name in statement.index:

                row = statement.loc[name]

                if len(row) > 0:

                    value = row.iloc[0]

                    result = _num(value)

                    if result is not None:
                        return result

    except Exception:
        pass

    return None


def _calculate_roic(
    operating_income: float | None,
    total_debt: float | None,
    equity: float | None,
    cash: float | None,
) -> float | None:

    if operating_income is None:
        return None

    if equity is None:
        return None

    debt = total_debt or 0.0
    cash_value = cash or 0.0

    invested_capital = debt + equity - cash_value

    if invested_capital <= 0:
        return None

    return operating_income / invested_capital


def fetch_stock(
    ticker: str,
) -> StockRecord:

    symbol = ticker.upper().strip()

    yf_ticker = yf.Ticker(symbol)

    info = yf_ticker.get_info()

    # --------------------------------------------------------
    # Basic values
    # --------------------------------------------------------

    market_cap = _num(
        _safe(info, "marketCap")
    )

    price = _num(
        _safe(
            info,
            "currentPrice",
            "regularMarketPrice",
            "previousClose",
        )
    )

    total_cash = _num(
        _safe(
            info,
            "totalCash",
            "cash",
        )
    )

    total_debt = _num(
        _safe(
            info,
            "totalDebt",
        )
    )

    net_debt = None

    if total_debt is not None and total_cash is not None:
        net_debt = total_debt - total_cash

    # --------------------------------------------------------
    # Financial statements
    # --------------------------------------------------------

    income_statement = None
    balance_sheet = None
    cashflow_statement = None

    try:
        income_statement = yf_ticker.financials
    except Exception:
        pass

    try:
        balance_sheet = yf_ticker.balance_sheet
    except Exception:
        pass

    try:
        cashflow_statement = yf_ticker.cashflow
    except Exception:
        pass

    operating_income = _statement_value(
        income_statement,
        [
            "Operating Income",
            "OperatingIncome",
        ],
    )

    equity = _statement_value(
        balance_sheet,
        [
            "Stockholders Equity",
            "StockholdersEquity",
            "Common Stock Equity",
            "CommonStockEquity",
        ],
    )

    statement_debt = _statement_value(
        balance_sheet,
        [
            "Total Debt",
            "TotalDebt",
        ],
    )

    statement_cash = _statement_value(
        balance_sheet,
        [
            "Cash Cash Equivalents And Short Term Investments",
            "CashAndCashEquivalents",
            "Cash Cash Equivalents And Short Term Investments",
        ],
    )

    if total_debt is None:
        total_debt = statement_debt

    if total_cash is None:
        total_cash = statement_cash

    if (
        total_debt is not None
        and total_cash is not None
    ):
        net_debt = total_debt - total_cash

    roic = _calculate_roic(
        operating_income=operating_income,
        total_debt=total_debt,
        equity=equity,
        cash=total_cash,
    )

    roe = _num(
        _safe(info, "returnOnEquity")
    )

    roa = _num(
        _safe(info, "returnOnAssets")
    )

    fcf = _num(
        _safe(info, "freeCashflow")
    )

    fcf_yield = None

    if (
        fcf is not None
        and market_cap is not None
        and market_cap > 0
    ):
        fcf_yield = fcf / market_cap

    # --------------------------------------------------------
    # Build record
    # --------------------------------------------------------

    record = StockRecord(

        ticker=symbol,

        company_name=str(
            _safe(
                info,
                "longName",
                "shortName",
            ) or ""
        ),

        exchange=str(
            _safe(
                info,
                "exchange",
                "fullExchangeName",
            ) or ""
        ),

        sector=str(
            _safe(
                info,
                "sector",
            ) or ""
        ),

        industry=str(
            _safe(
                info,
                "industry",
            ) or ""
        ),

        market_cap=market_cap,
        price=price,

        revenue=_num(
            _safe(
                info,
                "totalRevenue",
            )
        ),

        revenue_growth=_num(
            _safe(
                info,
                "revenueGrowth",
            )
        ),

        gross_margin=_num(
            _safe(
                info,
                "grossMargins",
            )
        ),

        operating_margin=_num(
            _safe(
                info,
                "operatingMargins",
            )
        ),

        profit_margin=_num(
            _safe(
                info,
                "profitMargins",
            )
        ),

        eps=_num(
            _safe(
                info,
                "trailingEps",
            )
        ),

        eps_growth=_num(
            _safe(
                info,
                "earningsGrowth",
            )
        ),

        free_cash_flow=fcf,

        fcf_yield=fcf_yield,

        roe=roe,

        roa=roa,

        roic=roic,

        total_cash=total_cash,

        total_debt=total_debt,

        net_debt=net_debt,

        debt_to_equity=_num(
            _safe(
                info,
                "debtToEquity",
            )
        ),

        current_ratio=_num(
            _safe(
                info,
                "currentRatio",
            )
        ),

        pe=_num(
            _safe(
                info,
                "trailingPE",
            )
        ),

        forward_pe=_num(
            _safe(
                info,
                "forwardPE",
            )
        ),

        peg=_num(
            _safe(
                info,
                "pegRatio",
            )
        ),

        price_to_sales=_num(
            _safe(
                info,
                "priceToSalesTrailing12Months",
            )
        ),

        price_to_book=_num(
            _safe(
                info,
                "priceToBook",
            )
        ),

        ev_to_ebitda=_num(
            _safe(
                info,
                "enterpriseToEbitda",
            )
        ),

        beta=_num(
            _safe(
                info,
                "beta",
            )
        ),

        fifty_two_week_high=_num(
            _safe(
                info,
                "fiftyTwoWeekHigh",
            )
        ),

        fifty_two_week_low=_num(
            _safe(
                info,
                "fiftyTwoWeekLow",
            )
        ),

        dividend_yield=_num(
            _safe(
                info,
                "dividendYield",
            )
        ),

        payout_ratio=_num(
            _safe(
                info,
                "payoutRatio",
            )
        ),

        analyst_target_mean=_num(
            _safe(
                info,
                "targetMeanPrice",
            )
        ),

        analyst_recommendation=str(
            _safe(
                info,
                "recommendationKey",
            ) or ""
        ),

        shares_outstanding=_num(
            _safe(
                info,
                "sharesOutstanding",
            )
        ),

        source="yfinance",

        fetched_at=datetime.now(
            timezone.utc
        ).isoformat(),
    )

    # --------------------------------------------------------
    # Data completeness
    # --------------------------------------------------------

    fields = [

        record.market_cap,
        record.price,

        record.revenue,
        record.revenue_growth,

        record.gross_margin,
        record.operating_margin,
        record.profit_margin,

        record.eps,
        record.eps_growth,

        record.free_cash_flow,

        record.roe,
        record.roa,
        record.roic,

        record.total_cash,
        record.total_debt,
        record.net_debt,

        record.debt_to_equity,
        record.current_ratio,

        record.pe,
        record.forward_pe,
        record.peg,
        record.price_to_sales,
        record.price_to_book,
        record.ev_to_ebitda,

        record.beta,

        record.fifty_two_week_high,
        record.fifty_two_week_low,

    ]

    record.data_completeness = (
        sum(
            value is not None
            for value in fields
        )
        / len(fields)
    )

    # Confidence initially follows completeness.
    # Later ATLAS can incorporate source reliability,
    # freshness and cross-source validation.
    record.data_confidence = record.data_completeness

    return record

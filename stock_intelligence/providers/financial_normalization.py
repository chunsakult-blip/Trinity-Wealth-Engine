from __future__ import annotations

from typing import Any, Mapping, Optional

from .financial_model import (
    FinancialPeriod,
    FinancialProvenance,
    NormalizedFinancials,
)


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_div(
    numerator: Optional[float],
    denominator: Optional[float],
) -> Optional[float]:

    if numerator is None or denominator is None:
        return None

    if denominator == 0:
        return None

    return numerator / denominator


def _add_provenance(
    period: FinancialPeriod,
    field: str,
    raw_value: Any,
    normalized_value: Any,
    source: str = "SEC",
    source_url: Optional[str] = None,
    accession: Optional[str] = None,
    retrieved_at: Optional[str] = None,
) -> None:

    period.provenance.append(
        FinancialProvenance(
            ticker=period.ticker,
            field=field,
            period=period.fiscal_period,
            source=source,
            source_url=source_url,
            accession=accession,
            retrieved_at=retrieved_at,
            raw_value=raw_value,
            normalized_value=normalized_value,
        )
    )


def normalize_financial_period(
    ticker: str,
    fiscal_period: str,
    raw: Mapping[str, Any],
    *,
    source: str = "SEC",
    source_url: Optional[str] = None,
    accession: Optional[str] = None,
    retrieved_at: Optional[str] = None,
) -> FinancialPeriod:

    revenue = _number(raw.get("revenue"))
    eps = _number(raw.get("eps"))
    gross_profit = _number(raw.get("gross_profit"))
    operating_income = _number(raw.get("operating_income"))
    net_income = _number(raw.get("net_income"))

    ocf = _number(raw.get("ocf"))
    capex = _number(raw.get("capex"))
    fcf = _number(raw.get("fcf"))

    if fcf is None and ocf is not None and capex is not None:
        fcf = ocf - abs(capex)

    cash = _number(raw.get("cash"))
    debt = _number(raw.get("debt"))
    assets = _number(raw.get("assets"))
    equity = _number(raw.get("equity"))
    shares = _number(raw.get("shares"))

    roe = _safe_div(net_income, equity)
    roa = _safe_div(net_income, assets)

    tax_rate = _number(raw.get("tax_rate"))

    if operating_income is not None:
        if tax_rate is not None:
            nopat = operating_income * (1.0 - tax_rate)
        else:
            nopat = operating_income
    else:
        nopat = None

    invested_capital = None

    if equity is not None or debt is not None:
        invested_capital = (
            (equity or 0.0)
            + (debt or 0.0)
            - (cash or 0.0)
        )

    roic = _safe_div(nopat, invested_capital)

    gross_margin = _safe_div(gross_profit, revenue)
    operating_margin = _safe_div(operating_income, revenue)
    net_margin = _safe_div(net_income, revenue)

    debt_to_equity = _safe_div(debt, equity)

    net_debt = None

    if debt is not None or cash is not None:
        net_debt = (
            (debt or 0.0)
            - (cash or 0.0)
        )

    period = FinancialPeriod(
        ticker=ticker,
        fiscal_period=fiscal_period,

        revenue=revenue,
        eps=eps,
        gross_profit=gross_profit,
        operating_income=operating_income,
        net_income=net_income,

        ocf=ocf,
        capex=capex,
        fcf=fcf,

        cash=cash,
        debt=debt,
        assets=assets,
        equity=equity,

        shares=shares,

        roe=roe,
        roa=roa,
        roic=roic,

        gross_margin=gross_margin,
        operating_margin=operating_margin,
        net_margin=net_margin,

        debt_to_equity=debt_to_equity,
        net_debt=net_debt,
    )

    supplied_fields = [
        "revenue",
        "eps",
        "gross_profit",
        "operating_income",
        "net_income",
        "ocf",
        "capex",
        "fcf",
        "cash",
        "debt",
        "assets",
        "equity",
        "shares",
    ]

    for field_name in supplied_fields:

        raw_value = raw.get(field_name)

        if raw_value is not None:
            _add_provenance(
                period,
                field_name,
                raw_value,
                getattr(period, field_name),
                source=source,
                source_url=source_url,
                accession=accession,
                retrieved_at=retrieved_at,
            )

    derived_fields = [
        "roe",
        "roa",
        "roic",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "debt_to_equity",
        "net_debt",
    ]

    for field_name in derived_fields:

        _add_provenance(
            period,
            field_name,
            None,
            getattr(period, field_name),
            source=source,
            source_url=source_url,
            accession=accession,
            retrieved_at=retrieved_at,
        )

    return period


def normalize_financials(
    ticker: str,
    raw_periods: list[Mapping[str, Any]],
    *,
    source: str = "SEC",
) -> NormalizedFinancials:

    periods: list[FinancialPeriod] = []

    for raw in raw_periods:

        fiscal_period = str(
            raw.get("fiscal_period", "")
        )

        if not fiscal_period:
            raise ValueError(
                "Each financial period requires fiscal_period"
            )

        periods.append(
            normalize_financial_period(
                ticker=ticker,
                fiscal_period=fiscal_period,
                raw=raw,
                source=source,
            )
        )

    return NormalizedFinancials(
        ticker=ticker,
        periods=periods,
    )

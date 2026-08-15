from __future__ import annotations

from typing import Any, Optional

from .financial_model import (
    FinancialPeriod,
    Provenance,
    derive_metrics,
    safe_float,
)


FIELD_ALIASES = {
    "revenue": [
        "revenue",
        "revenues",
        "sales",
        "sales_revenue",
        "revenue_from_contract_with_customer_excluding_assessed_tax",
    ],

    "eps": [
        "eps",
        "earnings_per_share",
        "basic_eps",
        "diluted_eps",
    ],

    "gross_profit": [
        "gross_profit",
    ],

    "operating_income": [
        "operating_income",
        "operating_income_loss",
    ],

    "net_income": [
        "net_income",
        "net_income_loss",
        "profit_loss",
    ],

    "ocf": [
        "ocf",
        "operating_cash_flow",
        "net_cash_provided_by_used_in_operating_activities",
    ],

    "capex": [
        "capex",
        "capital_expenditures",
        "payments_to_acquire_property_plant_and_equipment",
    ],

    "cash": [
        "cash",
        "cash_and_cash_equivalents",
        "cash_and_cash_equivalents_at_carrying_value",
    ],

    "debt": [
        "debt",
        "total_debt",
        "long_term_debt",
        "short_term_debt",
    ],

    "assets": [
        "assets",
        "total_assets",
    ],

    "equity": [
        "equity",
        "stockholders_equity",
        "shareholders_equity",
        "stockholders_equity_including_portion_attributable_to_noncontrolling_interest",
    ],

    "shares": [
        "shares",
        "shares_outstanding",
        "weighted_average_shares",
    ],
}


def normalize_key(key: str) -> str:
    return (
        str(key)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def find_value(
    raw: dict[str, Any],
    canonical_field: str,
) -> tuple[Optional[Any], Optional[str]]:

    normalized = {
        normalize_key(k): v
        for k, v in raw.items()
    }

    aliases = FIELD_ALIASES.get(
        canonical_field,
        [],
    )

    for alias in aliases:
        alias = normalize_key(alias)

        if alias in normalized:
            return (
                normalized[alias],
                alias,
            )

    return None, None


def normalize_period(
    raw: dict[str, Any],
    *,
    ticker: str,
    cik: Optional[str] = None,
    period: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    fiscal_period: Optional[str] = None,
    form: Optional[str] = None,
    filing_date: Optional[str] = None,
    source: str = "sec",
    source_url: Optional[str] = None,
    accession: Optional[str] = None,
) -> FinancialPeriod:

    if not period:
        raise ValueError(
            "period is required for normalization"
        )

    record = FinancialPeriod(
        ticker=ticker,
        cik=cik,
        period=period,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        form=form,
        filing_date=filing_date,
    )

    for field in FIELD_ALIASES:

        value, raw_field = find_value(
            raw,
            field,
        )

        if value is None:
            continue

        if field == "eps":
            normalized_value = safe_float(
                value
            )
        else:
            normalized_value = safe_float(
                value
            )

        setattr(
            record,
            field,
            normalized_value,
        )

        record.provenance[field] = Provenance(
            source=source,
            source_url=source_url,
            form=form,
            accession=accession,
            filing_date=filing_date,
            raw_field=raw_field,
        )

    # Derive FCF / margins / ROE / ROA / etc.
    derive_metrics(record)

    return record

"""
Canonical financial data models.

These models are provider-neutral. SEC-specific details must not leak
into downstream financial intelligence components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FinancialFact:
    concept: str
    value: float
    unit: str
    start: str | None
    end: str
    filed: str | None
    form: str | None
    fiscal_year: int | None
    fiscal_period: str | None
    frame: str | None
    source: str = "SEC"


@dataclass
class FinancialPeriod:
    period: str
    start: str | None
    end: str | None

    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    eps: float | None = None

    assets: float | None = None
    equity: float | None = None
    cash: float | None = None
    debt: float | None = None

    operating_cash_flow: float | None = None

    # Canonical convention:
    # CapEx is always represented as a POSITIVE cash outflow.
    capex: float | None = None

    free_cash_flow: float | None = None

    shares: float | None = None
    interest_expense: float | None = None


@dataclass
class FinancialQuality:
    score: float
    completeness: float
    freshness: float
    consistency: float
    confidence: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class NormalizedFinancials:
    cik: int | None
    ticker: str | None
    company_name: str | None
    currency: str | None

    latest_period: FinancialPeriod | None
    prior_period: FinancialPeriod | None

    # Currently represents the latest canonical trailing period
    # available from the provider. True TTM is populated only when
    # enough quarterly periods are available.
    ttm: FinancialPeriod | None

    periods: list[FinancialPeriod] = field(default_factory=list)

    metrics: dict[str, float | None] = field(
        default_factory=dict
    )

    quality: dict[str, Any] = field(
        default_factory=dict
    )

    evidence: list[dict[str, Any]] = field(
        default_factory=list
    )

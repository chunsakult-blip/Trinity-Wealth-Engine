from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FinancialProvenance:
    ticker: str
    field: str
    period: Optional[str]
    source: str
    source_url: Optional[str] = None
    accession: Optional[str] = None
    retrieved_at: Optional[str] = None
    raw_value: Any = None
    normalized_value: Any = None


@dataclass
class FinancialPeriod:
    ticker: str
    fiscal_period: str

    revenue: Optional[float] = None
    eps: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None

    ocf: Optional[float] = None
    capex: Optional[float] = None
    fcf: Optional[float] = None

    cash: Optional[float] = None
    debt: Optional[float] = None
    assets: Optional[float] = None
    equity: Optional[float] = None

    shares: Optional[float] = None

    roe: Optional[float] = None
    roa: Optional[float] = None
    roic: Optional[float] = None

    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None

    debt_to_equity: Optional[float] = None
    net_debt: Optional[float] = None

    provenance: list[FinancialProvenance] = field(
        default_factory=list
    )


@dataclass
class NormalizedFinancials:
    ticker: str

    periods: list[FinancialPeriod] = field(
        default_factory=list
    )

    def get_period(
        self,
        fiscal_period: str,
    ) -> Optional[FinancialPeriod]:

        for period in self.periods:

            if period.fiscal_period == fiscal_period:
                return period

        return None

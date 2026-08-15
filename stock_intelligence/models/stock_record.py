from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class StockRecord:

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    ticker: str
    company_name: str = ""
    exchange: str = ""
    sector: str = ""
    industry: str = ""

    # --------------------------------------------------------
    # Market
    # --------------------------------------------------------

    market_cap: float | None = None
    price: float | None = None

    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None

    beta: float | None = None

    # --------------------------------------------------------
    # Income / Growth
    # --------------------------------------------------------

    revenue: float | None = None
    revenue_growth: float | None = None

    gross_margin: float | None = None
    operating_margin: float | None = None
    profit_margin: float | None = None

    eps: float | None = None
    eps_growth: float | None = None

    # --------------------------------------------------------
    # Cash Flow
    # --------------------------------------------------------

    free_cash_flow: float | None = None
    fcf_growth: float | None = None
    fcf_yield: float | None = None

    # --------------------------------------------------------
    # Returns
    # --------------------------------------------------------

    roe: float | None = None
    roa: float | None = None
    roic: float | None = None

    # --------------------------------------------------------
    # Balance Sheet
    # --------------------------------------------------------

    total_cash: float | None = None
    total_debt: float | None = None
    net_debt: float | None = None

    debt_to_equity: float | None = None
    current_ratio: float | None = None

    # --------------------------------------------------------
    # Valuation
    # --------------------------------------------------------

    pe: float | None = None
    forward_pe: float | None = None
    peg: float | None = None
    price_to_sales: float | None = None
    price_to_book: float | None = None
    ev_to_ebitda: float | None = None

    # --------------------------------------------------------
    # Dividend
    # --------------------------------------------------------

    dividend_yield: float | None = None
    payout_ratio: float | None = None

    # --------------------------------------------------------
    # Analysts
    # --------------------------------------------------------

    analyst_target_mean: float | None = None
    analyst_recommendation: str = ""
    shares_outstanding: float | None = None

    # --------------------------------------------------------
    # Nick Scores
    # --------------------------------------------------------

    quality_score: float = 0.0
    growth_score: float = 0.0
    financial_health_score: float = 0.0
    valuation_score: float = 0.0
    momentum_score: float = 0.0

    composite_score: float = 0.0

    # --------------------------------------------------------
    # Risk / Confidence
    # --------------------------------------------------------

    data_completeness: float = 0.0
    data_confidence: float = 0.0

    risk_flags: str = ""

    # --------------------------------------------------------
    # Verdict
    # --------------------------------------------------------

    tier: str = "TIER_3"
    decision: str = "WATCH"

    business_quality: str = "UNKNOWN"

    hard_failures: str = ""

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    source: str = ""
    fetched_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

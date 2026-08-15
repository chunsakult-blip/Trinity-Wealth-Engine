from __future__ import annotations

import math

from stock_intelligence.models import StockRecord
from stock_intelligence.rules.nick_rules import (
    DEFAULT_NICK_RULES,
    NickRuleConfig,
)


def clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:

    return max(
        low,
        min(high, value),
    )


def growth_score(
    value: float | None,
) -> float:

    if value is None:
        return 0.0

    if value <= 0:
        return 0.0

    # Smooth diminishing returns.
    #
    # 10%  -> ~33
    # 25%  -> ~63
    # 50%  -> ~86
    # 100% -> ~98
    #
    # This prevents all high-growth companies from
    # immediately becoming identical 100/100 scores.

    score = 100.0 * (
        1.0 - math.exp(
            -value / 0.25
        )
    )

    return clamp(score)


def return_score(
    value: float | None,
    excellent: float,
) -> float:

    if value is None:
        return 0.0

    if value <= 0:
        return 0.0

    return clamp(
        value / excellent * 100.0
    )


def margin_score(
    value: float | None,
    excellent: float,
) -> float:

    if value is None:
        return 0.0

    if value <= 0:
        return 0.0

    return clamp(
        value / excellent * 100.0
    )


def lower_better(
    value: float | None,
    worst: float,
) -> float:

    if value is None:
        return 50.0

    if value <= 0:
        return 100.0

    if worst <= 0:
        return 0.0

    value = min(
        float(value),
        worst,
    )

    return clamp(
        (worst - value)
        / worst
        * 100.0
    )


def score_fcf_yield(
    value: float | None,
) -> float:

    if value is None:
        return 50.0

    if value <= 0:
        return 0.0

    # 2% = 40
    # 5% = 70
    # 10% = 100
    return clamp(
        value / 0.10 * 100.0
    )


def screen_stock(
    stock: StockRecord,
    rules: NickRuleConfig = DEFAULT_NICK_RULES,
) -> StockRecord:

    # ========================================================
    # QUALITY
    # ========================================================

    quality_components = [

        return_score(
            stock.roe,
            0.30,
        ),

        return_score(
            stock.roic,
            0.20,
        ),

        margin_score(
            stock.operating_margin,
            0.30,
        ),

        margin_score(
            stock.profit_margin,
            0.30,
        ),

        margin_score(
            stock.gross_margin,
            0.70,
        ),

    ]

    stock.quality_score = sum(
        quality_components
    ) / len(
        quality_components
    )

    # ========================================================
    # GROWTH
    # ========================================================

    growth_components = [

        growth_score(
            stock.revenue_growth
        ),

        growth_score(
            stock.eps_growth
        ),

    ]

    stock.growth_score = sum(
        growth_components
    ) / len(
        growth_components
    )

    # ========================================================
    # FINANCIAL HEALTH
    # ========================================================

    health_components = []

    # Net debt
    if (
        stock.net_debt is not None
    ):

        if stock.net_debt <= 0:
            net_debt_score = 100.0

        elif stock.market_cap:
            net_debt_ratio = (
                stock.net_debt
                / stock.market_cap
            )

            net_debt_score = clamp(
                100.0
                - net_debt_ratio * 200.0
            )

        else:
            net_debt_score = 50.0

        health_components.append(
            net_debt_score
        )

    # Current ratio
    if (
        stock.current_ratio
        is not None
    ):

        current_score = clamp(
            stock.current_ratio
            / 2.0
            * 100.0
        )

        health_components.append(
            current_score
        )

    # Cash / debt
    if (
        stock.total_cash is not None
        and stock.total_debt is not None
        and stock.total_debt > 0
    ):

        cash_debt_ratio = (
            stock.total_cash
            / stock.total_debt
        )

        cash_debt_score = clamp(
            cash_debt_ratio
            / 2.0
            * 100.0
        )

        health_components.append(
            cash_debt_score
        )

    if health_components:

        stock.financial_health_score = (
            sum(health_components)
            / len(health_components)
        )

    else:

        stock.financial_health_score = 50.0

    # ========================================================
    # VALUATION
    # ========================================================

    valuation_components = []

    pe = (
        stock.forward_pe
        if stock.forward_pe is not None
        else stock.pe
    )

    if pe is not None:
        valuation_components.append(
            lower_better(
                pe,
                rules.max_pe_for_full_score,
            )
        )

    if stock.ev_to_ebitda is not None:

        valuation_components.append(
            lower_better(
                stock.ev_to_ebitda,
                rules.max_ev_ebitda_for_full_score,
            )
        )

    if stock.peg is not None:

        if stock.peg <= 0:
            peg_score = 100.0

        else:
            peg_score = clamp(
                100.0
                - stock.peg * 50.0
            )

        valuation_components.append(
            peg_score
        )

    if stock.fcf_yield is not None:

        valuation_components.append(
            score_fcf_yield(
                stock.fcf_yield
            )
        )

    if valuation_components:

        stock.valuation_score = (
            sum(valuation_components)
            / len(valuation_components)
        )

    else:

        stock.valuation_score = 50.0

    # ========================================================
    # MOMENTUM
    # ========================================================

    if (
        stock.price is not None
        and stock.fifty_two_week_low is not None
        and stock.fifty_two_week_high is not None
        and stock.fifty_two_week_high
        > stock.fifty_two_week_low
    ):

        position = (
            stock.price
            - stock.fifty_two_week_low
        ) / (
            stock.fifty_two_week_high
            - stock.fifty_two_week_low
        )

        stock.momentum_score = clamp(
            position * 100.0
        )

    else:

        stock.momentum_score = 50.0

    # ========================================================
    # COMPOSITE
    # ========================================================

    stock.composite_score = (

        stock.quality_score
        * rules.quality_weight

        + stock.growth_score
        * rules.growth_weight

        + stock.financial_health_score
        * rules.financial_health_weight

        + stock.valuation_score
        * rules.valuation_weight

        + stock.momentum_score
        * rules.momentum_weight
    )

    # ========================================================
    # RISK FLAGS
    # ========================================================

    risks = []
    failures = []

    sector_lower = (
        stock.sector
        or ""
    ).lower()

    is_financial = any(
        keyword in sector_lower
        for keyword in [
            "financial",
            "bank",
        ]
    )

    # --------------------------------------------------------
    # Data
    # --------------------------------------------------------

    if (
        stock.data_completeness
        < rules.minimum_data_completeness
    ):

        failures.append(
            "INSUFFICIENT_DATA"
        )

    # --------------------------------------------------------
    # Leverage
    #
    # IMPORTANT:
    # Financial institutions naturally carry high leverage.
    # Therefore D/E is NOT treated as a generic hard failure
    # for financial companies.
    # --------------------------------------------------------

    if (
        not is_financial
        and stock.debt_to_equity is not None
        and stock.debt_to_equity
        > rules.max_debt_to_equity
    ):

        # Net cash companies should not be automatically
        # rejected simply because equity is small.
        if (
            stock.net_debt is not None
            and stock.net_debt > 0
        ):

            failures.append(
                "HIGH_LEVERAGE"
            )

            risks.append(
                "HIGH_LEVERAGE"
            )

        else:

            risks.append(
                "HIGH_D_E_BUT_NET_CASH"
            )

    # --------------------------------------------------------
    # Current ratio
    # --------------------------------------------------------

    if (
        not is_financial
        and stock.current_ratio is not None
        and stock.current_ratio
        < rules.min_current_ratio
    ):

        failures.append(
            "LOW_CURRENT_RATIO"
        )

        risks.append(
            "LOW_CURRENT_RATIO"
        )

    # --------------------------------------------------------
    # Valuation
    # --------------------------------------------------------

    if (
        pe is not None
        and pe > 35
    ):

        risks.append(
            "HIGH_PE"
        )

    if (
        stock.ev_to_ebitda is not None
        and stock.ev_to_ebitda > 30
    ):

        risks.append(
            "HIGH_EV_EBITDA"
        )

    if (
        stock.peg is not None
        and stock.peg > 2
    ):

        risks.append(
            "HIGH_PEG"
        )

    # --------------------------------------------------------
    # FCF
    # --------------------------------------------------------

    if (
        stock.free_cash_flow is not None
        and stock.free_cash_flow < 0
    ):

        risks.append(
            "NEGATIVE_FCF"
        )

    # --------------------------------------------------------
    # Growth
    # --------------------------------------------------------

    if (
        stock.revenue_growth is not None
        and stock.revenue_growth < 0
    ):

        risks.append(
            "REVENUE_DECLINE"
        )

    # ========================================================
    # VERDICT
    # ========================================================

    stock.hard_failures = ",".join(
        failures
    )

    stock.risk_flags = ",".join(
        risks
    )

    # --------------------------------------------------------
    # Business quality label
    # --------------------------------------------------------

    if (
        stock.quality_score
        >= rules.excellent_quality
    ):

        stock.business_quality = (
            "EXCELLENT"
        )

    elif (
        stock.quality_score
        >= rules.strong_quality
    ):

        stock.business_quality = (
            "STRONG"
        )

    elif stock.quality_score >= 50:

        stock.business_quality = (
            "AVERAGE"
        )

    else:

        stock.business_quality = (
            "WEAK"
        )

    # --------------------------------------------------------
    # Tier
    # --------------------------------------------------------

    if (
        "INSUFFICIENT_DATA"
        in failures
    ):

        stock.tier = "TIER_3"
        stock.decision = "WATCH"

    elif failures:

        if (
            stock.composite_score
            >= rules.tier2_score
        ):

            stock.tier = "TIER_2"
            stock.decision = "REVIEW"

        else:

            stock.tier = "TIER_3"
            stock.decision = "WATCH"

    elif (
        stock.composite_score
        >= rules.tier1_score
    ):

        stock.tier = "TIER_1"
        stock.decision = "NICK_CANDIDATE"

    elif (
        stock.composite_score
        >= rules.tier2_score
    ):

        stock.tier = "TIER_2"
        stock.decision = "REVIEW"

    else:

        stock.tier = "TIER_3"
        stock.decision = "WATCH"

    return stock

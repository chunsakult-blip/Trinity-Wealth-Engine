"""
Provider-neutral deterministic valuation layer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValuationResult:
    score: float
    pe: float | None
    ev_ebitda: float | None
    price_to_fcf: float | None
    fcf_yield: float | None
    earnings_yield: float | None
    margin_of_safety: float | None
    warnings: list[str]


class ValuationEngine:

    def calculate(
        self,
        metrics: dict[str, float | None],
        *,
        market_cap: float | None = None,
        enterprise_value: float | None = None,
    ) -> ValuationResult:

        warnings: list[str] = []

        net_income = metrics.get("net_income")
        free_cash_flow = metrics.get("free_cash_flow")
        operating_income = metrics.get("operating_income")

        # ------------------------------------------------------------
        # P/E
        # ------------------------------------------------------------

        pe = None

        if (
            market_cap is not None
            and market_cap > 0
            and net_income is not None
            and net_income > 0
        ):
            pe = market_cap / net_income

        # ------------------------------------------------------------
        # EV / EBITDA
        # ------------------------------------------------------------

        ev_ebitda = None

        if (
            enterprise_value is not None
            and enterprise_value > 0
            and operating_income is not None
            and operating_income > 0
        ):
            ev_ebitda = enterprise_value / operating_income

        # ------------------------------------------------------------
        # PRICE / FCF
        # ------------------------------------------------------------

        price_to_fcf = None

        if (
            market_cap is not None
            and market_cap > 0
            and free_cash_flow is not None
            and free_cash_flow > 0
        ):
            price_to_fcf = market_cap / free_cash_flow

        # ------------------------------------------------------------
        # FCF YIELD
        # ------------------------------------------------------------

        fcf_yield = None

        if (
            market_cap is not None
            and market_cap > 0
            and free_cash_flow is not None
        ):
            fcf_yield = free_cash_flow / market_cap

        # ------------------------------------------------------------
        # EARNINGS YIELD
        # ------------------------------------------------------------

        earnings_yield = None

        if (
            market_cap is not None
            and market_cap > 0
            and net_income is not None
        ):
            earnings_yield = net_income / market_cap

        # ------------------------------------------------------------
        # VALUATION SCORE
        # ------------------------------------------------------------

        components: list[float] = []

        if pe is not None:
            if pe <= 12:
                components.append(100.0)
            elif pe <= 16:
                components.append(90.0)
            elif pe <= 20:
                components.append(80.0)
            elif pe <= 25:
                components.append(65.0)
            elif pe <= 35:
                components.append(45.0)
            else:
                components.append(20.0)

        if price_to_fcf is not None:
            if price_to_fcf <= 12:
                components.append(100.0)
            elif price_to_fcf <= 15:
                components.append(90.0)
            elif price_to_fcf <= 20:
                components.append(80.0)
            elif price_to_fcf <= 25:
                components.append(65.0)
            elif price_to_fcf <= 35:
                components.append(45.0)
            else:
                components.append(20.0)

        if fcf_yield is not None:
            if fcf_yield >= 0.10:
                components.append(100.0)
            elif fcf_yield >= 0.08:
                components.append(90.0)
            elif fcf_yield >= 0.06:
                components.append(80.0)
            elif fcf_yield >= 0.04:
                components.append(65.0)
            elif fcf_yield >= 0.025:
                components.append(45.0)
            else:
                components.append(20.0)

        if earnings_yield is not None:
            if earnings_yield >= 0.10:
                components.append(100.0)
            elif earnings_yield >= 0.08:
                components.append(90.0)
            elif earnings_yield >= 0.06:
                components.append(80.0)
            elif earnings_yield >= 0.04:
                components.append(65.0)
            elif earnings_yield >= 0.025:
                components.append(45.0)
            else:
                components.append(20.0)

        if components:
            score = sum(components) / len(components)
        else:
            score = 0.0
            warnings.append(
                "Insufficient valuation inputs."
            )

        # ------------------------------------------------------------
        # MARGIN OF SAFETY
        # ------------------------------------------------------------

        margin_of_safety = None

        if pe is not None:
            fair_pe = 20.0
            margin_of_safety = 1.0 - (pe / fair_pe)

        if market_cap is None:
            warnings.append(
                "Market capitalization unavailable."
            )

        if free_cash_flow is None:
            warnings.append(
                "Free cash flow unavailable."
            )

        return ValuationResult(
            score=score,
            pe=pe,
            ev_ebitda=ev_ebitda,
            price_to_fcf=price_to_fcf,
            fcf_yield=fcf_yield,
            earnings_yield=earnings_yield,
            margin_of_safety=margin_of_safety,
            warnings=warnings,
        )

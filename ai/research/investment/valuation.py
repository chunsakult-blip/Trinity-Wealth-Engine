"""
Provider-neutral deterministic valuation layer.

Canonical valuation contract.

Important:
    EV / EBITDA must use EBITDA.

    Operating income is EBIT, not EBITDA.

Therefore this engine will NEVER silently calculate:

    EV / operating_income

and label it:

    EV / EBITDA

If EBITDA is unavailable, ev_ebitda remains None and a warning
is emitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        metrics: dict[str, Any],
        *,
        market_cap: float | None = None,
        enterprise_value: float | None = None,
    ) -> ValuationResult:

        metrics = metrics or {}

        warnings: list[str] = []

        net_income = metrics.get(
            "net_income"
        )

        free_cash_flow = metrics.get(
            "free_cash_flow"
        )

        # ------------------------------------------------------------
        # EBITDA
        #
        # Prefer canonical EBITDA.
        #
        # If unavailable, derive:
        #
        # EBITDA = EBIT + D&A
        #
        # using canonical operating_income plus
        # depreciation_and_amortization when available.
        #
        # Never substitute EBIT alone.
        # ------------------------------------------------------------

        ebitda = metrics.get(
            "ebitda"
        )

        if ebitda is None:

            operating_income = metrics.get(
                "operating_income"
            )

            depreciation_and_amortization = (
                metrics.get(
                    "depreciation_and_amortization"
                )
            )

            if (
                operating_income is not None
                and depreciation_and_amortization is not None
            ):
                ebitda = (
                    operating_income
                    + abs(
                        depreciation_and_amortization
                    )
                )

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
            pe = (
                market_cap
                / net_income
            )

        # ------------------------------------------------------------
        # EV / EBITDA
        # ------------------------------------------------------------

        ev_ebitda = None

        if (
            enterprise_value is not None
            and enterprise_value > 0
            and ebitda is not None
            and ebitda > 0
        ):
            ev_ebitda = (
                enterprise_value
                / ebitda
            )

        elif enterprise_value is not None:

            warnings.append(
                "EBITDA unavailable; EV/EBITDA not calculated."
            )

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
            price_to_fcf = (
                market_cap
                / free_cash_flow
            )

        # ------------------------------------------------------------
        # FCF YIELD
        # ------------------------------------------------------------

        fcf_yield = None

        if (
            market_cap is not None
            and market_cap > 0
            and free_cash_flow is not None
        ):
            fcf_yield = (
                free_cash_flow
                / market_cap
            )

        # ------------------------------------------------------------
        # EARNINGS YIELD
        # ------------------------------------------------------------

        earnings_yield = None

        if (
            market_cap is not None
            and market_cap > 0
            and net_income is not None
        ):
            earnings_yield = (
                net_income
                / market_cap
            )

        # ------------------------------------------------------------
        # VALUATION SCORE
        #
        # Score only metrics that actually exist.
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

        if ev_ebitda is not None:

            if ev_ebitda <= 10:
                components.append(100.0)

            elif ev_ebitda <= 14:
                components.append(90.0)

            elif ev_ebitda <= 18:
                components.append(80.0)

            elif ev_ebitda <= 22:
                components.append(65.0)

            elif ev_ebitda <= 30:
                components.append(45.0)

            else:
                components.append(20.0)

        # PRICE / FCF is reporting-only.
        #
        # It is mathematically the inverse of FCF yield, so scoring
        # both would double-count the same valuation signal.
        # Keep price_to_fcf in the result for transparency, but do not
        # add it to the valuation score.

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

        # ------------------------------------------------------------
        # EARNINGS YIELD
        #
        # Reporting-only metric.
        #
        # Earnings yield is the inverse of P/E and therefore must not
        # be scored as an additional independent component. Including
        # both P/E and earnings yield would double-count the same
        # valuation signal.
        # ------------------------------------------------------------

        if components:
            score = (
                sum(components)
                / len(components)
            )

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

            margin_of_safety = (
                1.0
                - (pe / fair_pe)
            )

        # ------------------------------------------------------------
        # DATA WARNINGS
        # ------------------------------------------------------------

        if market_cap is None:

            warnings.append(
                "Market capitalization unavailable."
            )

        if free_cash_flow is None:

            warnings.append(
                "Free cash flow unavailable."
            )

        return ValuationResult(
            score=round(
                score,
                2,
            ),
            pe=pe,
            ev_ebitda=ev_ebitda,
            price_to_fcf=price_to_fcf,
            fcf_yield=fcf_yield,
            earnings_yield=earnings_yield,
            margin_of_safety=margin_of_safety,
            warnings=list(
                dict.fromkeys(
                    warnings
                )
            ),
        )

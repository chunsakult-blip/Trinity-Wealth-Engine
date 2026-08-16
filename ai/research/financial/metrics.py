"""
Provider-neutral deterministic financial metrics.
"""

from __future__ import annotations

from .models import NormalizedFinancials


class FinancialMetricsEngine:

    def calculate(
        self,
        financials: NormalizedFinancials,
    ) -> dict[str, float | None]:

        metrics = financials.metrics

        revenue = metrics.get("revenue")
        gross_profit = metrics.get("gross_profit")
        operating_income = metrics.get("operating_income")
        net_income = metrics.get("net_income")

        equity = metrics.get("equity")
        cash = metrics.get("cash")
        debt = metrics.get("debt")

        operating_cash_flow = metrics.get(
            "operating_cash_flow"
        )

        capex = metrics.get("capex")

        result: dict[str, float | None] = {}

        # ------------------------------------------------------------
        # MARGINS
        # ------------------------------------------------------------

        result["gross_margin"] = self._ratio(
            gross_profit,
            revenue,
        )

        result["operating_margin"] = self._ratio(
            operating_income,
            revenue,
        )

        result["net_margin"] = self._ratio(
            net_income,
            revenue,
        )

        # ------------------------------------------------------------
        # FREE CASH FLOW
        #
        # CapEx is canonicalized as a positive cash outflow.
        # ------------------------------------------------------------

        if (
            operating_cash_flow is not None
            and capex is not None
        ):
            result["free_cash_flow"] = (
                operating_cash_flow
                - abs(capex)
            )
        else:
            result["free_cash_flow"] = None

        # ------------------------------------------------------------
        # ROE
        # ------------------------------------------------------------

        result["roe"] = self._ratio(
            net_income,
            equity,
        )

        # ------------------------------------------------------------
        # ROIC
        # ------------------------------------------------------------

        tax_rate = metrics.get("tax_rate")

        invested_capital = self._add(
            equity,
            debt,
        )

        if (
            operating_income is not None
            and tax_rate is not None
            and invested_capital is not None
            and invested_capital != 0
        ):
            nopat = operating_income * (
                1.0 - tax_rate
            )

            result["roic"] = (
                nopat / invested_capital
            )
        else:
            result["roic"] = None

        # ------------------------------------------------------------
        # CAPITAL STRUCTURE
        # ------------------------------------------------------------

        result["debt_to_equity"] = self._ratio(
            debt,
            equity,
        )

        if (
            debt is not None
            and cash is not None
        ):
            result["net_debt"] = (
                debt - cash
            )
        else:
            result["net_debt"] = None

        # ------------------------------------------------------------
        # INTEREST COVERAGE
        # ------------------------------------------------------------

        interest_expense = metrics.get(
            "interest_expense"
        )

        if (
            operating_income is not None
            and interest_expense is not None
            and interest_expense != 0
        ):
            result["interest_coverage"] = (
                operating_income
                / abs(interest_expense)
            )
        else:
            result["interest_coverage"] = None

        # ------------------------------------------------------------
        # GROWTH
        # ------------------------------------------------------------

        result["revenue_growth"] = metrics.get(
            "revenue_growth"
        )

        result["net_income_growth"] = metrics.get(
            "net_income_growth"
        )

        result["fcf_growth"] = metrics.get(
            "fcf_growth"
        )

        return result

    @staticmethod
    def _ratio(
        numerator: float | None,
        denominator: float | None,
    ) -> float | None:

        if numerator is None:
            return None

        if denominator is None:
            return None

        if denominator == 0:
            return None

        return numerator / denominator

    @staticmethod
    def _add(
        a: float | None,
        b: float | None,
    ) -> float | None:

        if a is None or b is None:
            return None

        return a + b

    @staticmethod
    def _subtract(
        a: float | None,
        b: float | None,
    ) -> float | None:

        if a is None or b is None:
            return None

        return a - b

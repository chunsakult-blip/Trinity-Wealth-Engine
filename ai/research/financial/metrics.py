from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai.research.financial.models import (
    FinancialPeriod,
    NormalizedFinancials,
)


@dataclass
class FinancialMetrics:
    revenue: Optional[float] = None
    net_income: Optional[float] = None

    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None

    fcf_margin: Optional[float] = None

    roe: Optional[float] = None
    debt_to_equity: Optional[float] = None

    interest_coverage: Optional[float] = None


class FinancialMetricsEngine:
    """
    Provider-neutral deterministic financial metrics engine.

    Contract:
        calculate() accepts NormalizedFinancials.

    Canonical source:
        NormalizedFinancials.metrics

    Period-level values are used only when a derived ratio requires
    fields that are not already present in the canonical metric map.
    """

    def calculate(
        self,
        financials: NormalizedFinancials | FinancialPeriod | None,
    ) -> FinancialMetrics:

        if financials is None:
            return FinancialMetrics()

        # ----------------------------------------------------------
        # CANONICAL NORMALIZED FINANCIALS
        # ----------------------------------------------------------

        if isinstance(financials, NormalizedFinancials):

            metrics = financials.metrics or {}

            period = (
                financials.ttm
                or financials.latest_period
            )

            revenue = metrics.get("revenue")
            net_income = metrics.get("net_income")

        # ----------------------------------------------------------
        # BACKWARD-COMPATIBLE PERIOD INPUT
        # ----------------------------------------------------------

        elif isinstance(financials, FinancialPeriod):

            period = financials

            revenue = getattr(
                period,
                "revenue",
                None,
            )

            net_income = getattr(
                period,
                "net_income",
                None,
            )

            metrics = {}

        else:
            return FinancialMetrics()

        # ----------------------------------------------------------
        # BASE VALUES
        # ----------------------------------------------------------

        if revenue is None and period is not None:
            revenue = getattr(
                period,
                "revenue",
                None,
            )

        if net_income is None and period is not None:
            net_income = getattr(
                period,
                "net_income",
                None,
            )

        # ----------------------------------------------------------
        # PERIOD VALUES
        # ----------------------------------------------------------

        gross_profit = (
            getattr(period, "gross_profit", None)
            if period is not None
            else None
        )

        operating_income = (
            getattr(period, "operating_income", None)
            if period is not None
            else None
        )

        free_cash_flow = (
            getattr(period, "free_cash_flow", None)
            if period is not None
            else None
        )

        equity = (
            getattr(period, "equity", None)
            if period is not None
            else None
        )

        debt = (
            getattr(period, "debt", None)
            if period is not None
            else None
        )

        interest_expense = (
            getattr(period, "interest_expense", None)
            if period is not None
            else None
        )

        # Prefer canonical metric values when available.

        gross_profit = (
            metrics.get("gross_profit")
            if metrics.get("gross_profit") is not None
            else gross_profit
        )

        operating_income = (
            metrics.get("operating_income")
            if metrics.get("operating_income") is not None
            else operating_income
        )

        free_cash_flow = (
            metrics.get("free_cash_flow")
            if metrics.get("free_cash_flow") is not None
            else free_cash_flow
        )

        equity = (
            metrics.get("total_equity")
            if metrics.get("total_equity") is not None
            else equity
        )

        debt = (
            metrics.get("debt")
            if metrics.get("debt") is not None
            else debt
        )

        interest_expense = (
            metrics.get("interest_expense")
            if metrics.get("interest_expense") is not None
            else interest_expense
        )

        # ----------------------------------------------------------
        # PROFITABILITY MARGINS
        # ----------------------------------------------------------

        gross_margin = metrics.get("gross_margin")
        operating_margin = metrics.get("operating_margin")
        net_margin = metrics.get("net_margin")
        fcf_margin = metrics.get("fcf_margin")

        if revenue is not None and revenue != 0:

            if gross_margin is None and gross_profit is not None:
                gross_margin = (
                    gross_profit / revenue
                )

            if (
                operating_margin is None
                and operating_income is not None
            ):
                operating_margin = (
                    operating_income / revenue
                )

            if net_margin is None and net_income is not None:
                net_margin = (
                    net_income / revenue
                )

            if (
                fcf_margin is None
                and free_cash_flow is not None
            ):
                fcf_margin = (
                    free_cash_flow / revenue
                )

        # ----------------------------------------------------------
        # RETURN ON EQUITY
        # ----------------------------------------------------------

        roe = metrics.get("roe")

        if (
            roe is None
            and net_income is not None
            and equity is not None
            and equity != 0
        ):
            roe = (
                net_income / equity
            )

        # ----------------------------------------------------------
        # DEBT TO EQUITY
        # ----------------------------------------------------------

        debt_to_equity = metrics.get(
            "debt_to_equity"
        )

        if (
            debt_to_equity is None
            and debt is not None
            and equity is not None
            and equity != 0
        ):
            debt_to_equity = (
                debt / equity
            )

        # ----------------------------------------------------------
        # INTEREST COVERAGE
        # ----------------------------------------------------------

        interest_coverage = metrics.get(
            "interest_coverage"
        )

        if (
            interest_coverage is None
            and operating_income is not None
            and interest_expense is not None
            and interest_expense != 0
        ):
            interest_coverage = (
                operating_income
                / abs(interest_expense)
            )

        return FinancialMetrics(
            revenue=revenue,
            net_income=net_income,
            gross_margin=gross_margin,
            operating_margin=operating_margin,
            net_margin=net_margin,
            fcf_margin=fcf_margin,
            roe=roe,
            debt_to_equity=debt_to_equity,
            interest_coverage=interest_coverage,
        )

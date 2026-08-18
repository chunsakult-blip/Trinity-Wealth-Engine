from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai.research.financial.models import FinancialPeriod


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
    Calculate canonical financial ratios from a FinancialPeriod.

    This layer is provider-neutral.
    SEC/XBRL-specific logic must remain in the normalizer.
    """

    def calculate(
        self,
        period: FinancialPeriod | None,
    ) -> FinancialMetrics:

        if period is None:
            return FinancialMetrics()

        revenue = period.revenue
        net_income = period.net_income

        gross_margin = None
        operating_margin = None
        net_margin = None
        fcf_margin = None
        roe = None
        debt_to_equity = None
        interest_coverage = None

        # --------------------------------------------------------------
        # PROFITABILITY MARGINS
        # --------------------------------------------------------------

        if revenue is not None and revenue != 0:

            if period.gross_profit is not None:
                gross_margin = (
                    period.gross_profit / revenue
                )

            if period.operating_income is not None:
                operating_margin = (
                    period.operating_income / revenue
                )

            if net_income is not None:
                net_margin = (
                    net_income / revenue
                )

            if period.free_cash_flow is not None:
                fcf_margin = (
                    period.free_cash_flow / revenue
                )

        # --------------------------------------------------------------
        # RETURN ON EQUITY
        # --------------------------------------------------------------

        if (
            net_income is not None
            and period.equity is not None
            and period.equity != 0
        ):
            roe = (
                net_income
                / period.equity
            )

        # --------------------------------------------------------------
        # DEBT TO EQUITY
        # --------------------------------------------------------------

        if (
            period.debt is not None
            and period.equity is not None
            and period.equity != 0
        ):
            debt_to_equity = (
                period.debt
                / period.equity
            )

        # --------------------------------------------------------------
        # INTEREST COVERAGE
        # --------------------------------------------------------------

        if (
            period.operating_income is not None
            and period.interest_expense is not None
            and period.interest_expense != 0
        ):
            interest_coverage = (
                period.operating_income
                / abs(period.interest_expense)
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

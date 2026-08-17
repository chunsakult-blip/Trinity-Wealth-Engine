from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai.research.financial.normalizer import FinancialPeriod


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

    def calculate(
        self,
        period: FinancialPeriod,
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


        if revenue:

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


        if (
            net_income is not None
            and period.equity
        ):
            roe = (
                net_income /
                period.equity
            )


        if (
            period.debt is not None
            and period.equity
        ):
            debt_to_equity = (
                period.debt /
                period.equity
            )


        if (
            period.operating_income is not None
            and period.interest_expense
        ):
            interest_coverage = (
                period.operating_income /
                abs(period.interest_expense)
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

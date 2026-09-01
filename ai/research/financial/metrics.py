from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai.research.financial.models import (
    FinancialPeriod,
    NormalizedFinancials,
)


@dataclass
class FinancialMetrics:
    """
    Canonical provider-neutral derived financial metrics.

    All ratio values are decimal ratios:
        0.20 == 20%

    Absolute financial values preserve the canonical provider scale.
    """

    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None

    operating_cash_flow: Optional[float] = None
    free_cash_flow: Optional[float] = None

    assets: Optional[float] = None
    equity: Optional[float] = None
    cash: Optional[float] = None
    debt: Optional[float] = None
    liabilities: Optional[float] = None

    interest_expense: Optional[float] = None

    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    fcf_margin: Optional[float] = None
    free_cashflow_margin: Optional[float] = None

    roe: Optional[float] = None
    roic: Optional[float] = None

    debt_to_equity: Optional[float] = None
    debt_to_asset: Optional[float] = None

    net_debt: Optional[float] = None
    interest_coverage: Optional[float] = None

    revenue_growth: Optional[float] = None
    net_income_growth: Optional[float] = None
    fcf_growth: Optional[float] = None


class FinancialMetricsEngine:
    """
    Provider-neutral deterministic financial metrics engine.

    Contract:
        calculate() accepts NormalizedFinancials.

    Canonical source:
        NormalizedFinancials.metrics

    Derived metrics are returned explicitly in FinancialMetrics so
    FinancialIntelligenceEngine can merge the complete metric set
    back into NormalizedFinancials.metrics.
    """

    def calculate(
        self,
        financials: NormalizedFinancials | FinancialPeriod | None,
    ) -> FinancialMetrics:

        if financials is None:
            return FinancialMetrics()

        if isinstance(financials, NormalizedFinancials):

            metrics = financials.metrics or {}

            period = (
                financials.ttm
                or financials.latest_period
            )

            prior = financials.prior_period

        elif isinstance(financials, FinancialPeriod):

            metrics = {}
            period = financials
            prior = None

        else:
            return FinancialMetrics()

        # ----------------------------------------------------------
        # BASE VALUES
        # ----------------------------------------------------------

        def value(key: str, attribute: str | None = None):
            result = metrics.get(key)

            if result is not None:
                return result

            if period is not None:
                return getattr(
                    period,
                    attribute or key,
                    None,
                )

            return None

        revenue = value("revenue")
        gross_profit = value("gross_profit")
        operating_income = value("operating_income")
        net_income = value("net_income")

        operating_cash_flow = value(
            "operating_cash_flow"
        )

        free_cash_flow = value(
            "free_cash_flow"
        )

        assets = value("assets")
        equity = value("total_equity", "equity")
        cash = value("cash")
        debt = value("debt")
        liabilities = value("liabilities")
        interest_expense = value(
            "interest_expense"
        )

        # ----------------------------------------------------------
        # PROFITABILITY MARGINS
        # ----------------------------------------------------------

        gross_margin = metrics.get("gross_margin")

        if (
            gross_margin is None
            and revenue not in (None, 0)
            and gross_profit is not None
        ):
            gross_margin = (
                gross_profit / revenue
            )

        operating_margin = metrics.get(
            "operating_margin"
        )

        if (
            operating_margin is None
            and revenue not in (None, 0)
            and operating_income is not None
        ):
            operating_margin = (
                operating_income / revenue
            )

        net_margin = metrics.get(
            "net_margin"
        )

        if (
            net_margin is None
            and revenue not in (None, 0)
            and net_income is not None
        ):
            net_margin = (
                net_income / revenue
            )

        fcf_margin = metrics.get(
            "fcf_margin"
        )

        if (
            fcf_margin is None
            and revenue not in (None, 0)
            and free_cash_flow is not None
        ):
            fcf_margin = (
                free_cash_flow / revenue
            )

        # Canonical alias used by the legacy quality layer.
        free_cashflow_margin = (
            metrics.get("free_cashflow_margin")
        )

        if free_cashflow_margin is None:
            free_cashflow_margin = fcf_margin

        # ----------------------------------------------------------
        # ROE
        # ----------------------------------------------------------

        roe = metrics.get("roe")

        if (
            roe is None
            and net_income is not None
            and equity not in (None, 0)
        ):
            roe = (
                net_income / equity
            )

        # ----------------------------------------------------------
        # ROIC
        #
        # Prefer an existing canonical value.
        #
        # Otherwise use:
        # NOPAT / invested capital
        #
        # with a deterministic approximation:
        # operating income * (1 - tax rate) / (equity + debt - cash)
        #
        # Tax rate is only used when supplied by the canonical metric map.
        # ----------------------------------------------------------

        roic = metrics.get("roic")

        if roic is None:

            # Canonical tax-rate field.
            #
            # Financial Intelligence currently publishes:
            #     tax_rate
            #
            # Accept effective_tax_rate only as a legacy
            # compatibility fallback.
            tax_rate = metrics.get("tax_rate")

            if tax_rate is None:
                tax_rate = metrics.get(
                    "effective_tax_rate"
                )

            invested_capital = None

            if (
                equity is not None
                and debt is not None
                and cash is not None
            ):
                invested_capital = (
                    equity
                    + debt
                    - cash
                )

            if (
                operating_income is not None
                and invested_capital is not None
                and invested_capital > 0
            ):

                if tax_rate is None:
                    tax_rate = 0.21

                tax_rate = max(
                    0.0,
                    min(1.0, tax_rate),
                )

                nopat = (
                    operating_income
                    * (1.0 - tax_rate)
                )

                roic = (
                    nopat
                    / invested_capital
                )

        # ----------------------------------------------------------
        # LEVERAGE
        # ----------------------------------------------------------

        debt_to_equity = metrics.get(
            "debt_to_equity"
        )

        if (
            debt_to_equity is None
            and debt is not None
            and equity not in (None, 0)
        ):
            debt_to_equity = (
                debt / equity
            )

        debt_to_asset = metrics.get(
            "debt_to_asset"
        )

        if (
            debt_to_asset is None
            and debt is not None
            and assets not in (None, 0)
        ):
            debt_to_asset = (
                debt / assets
            )

        net_debt = metrics.get(
            "net_debt"
        )

        if (
            net_debt is None
            and debt is not None
            and cash is not None
        ):
            net_debt = (
                debt - cash
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
            and interest_expense not in (None, 0)
        ):
            interest_coverage = (
                operating_income
                / abs(interest_expense)
            )

        # ----------------------------------------------------------
        # GROWTH
        #
        # Use prior normalized period where available.
        # ----------------------------------------------------------

        revenue_growth = metrics.get(
            "revenue_growth"
        )

        net_income_growth = metrics.get(
            "net_income_growth"
        )

        fcf_growth = metrics.get(
            "fcf_growth"
        )

        if prior is not None:

            prior_revenue = getattr(
                prior,
                "revenue",
                None,
            )

            prior_net_income = getattr(
                prior,
                "net_income",
                None,
            )

            prior_fcf = getattr(
                prior,
                "free_cash_flow",
                None,
            )

            if (
                revenue_growth is None
                and revenue is not None
                and prior_revenue not in (None, 0)
            ):
                revenue_growth = (
                    revenue / prior_revenue
                ) - 1.0

            if (
                net_income_growth is None
                and net_income is not None
                and prior_net_income not in (None, 0)
            ):
                net_income_growth = (
                    net_income
                    / prior_net_income
                ) - 1.0

            if (
                fcf_growth is None
                and free_cash_flow is not None
                and prior_fcf not in (None, 0)
            ):
                fcf_growth = (
                    free_cash_flow
                    / prior_fcf
                ) - 1.0

        return FinancialMetrics(
            revenue=revenue,
            gross_profit=gross_profit,
            operating_income=operating_income,
            net_income=net_income,

            operating_cash_flow=operating_cash_flow,
            free_cash_flow=free_cash_flow,

            assets=assets,
            equity=equity,
            cash=cash,
            debt=debt,
            liabilities=liabilities,

            interest_expense=interest_expense,

            gross_margin=gross_margin,
            operating_margin=operating_margin,
            net_margin=net_margin,
            fcf_margin=fcf_margin,
            free_cashflow_margin=free_cashflow_margin,

            roe=roe,
            roic=roic,

            debt_to_equity=debt_to_equity,
            debt_to_asset=debt_to_asset,

            net_debt=net_debt,
            interest_coverage=interest_coverage,

            revenue_growth=revenue_growth,
            net_income_growth=net_income_growth,
            fcf_growth=fcf_growth,
        )

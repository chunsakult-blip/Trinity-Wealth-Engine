from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NormalizedFinancials:

    ticker: str

    revenue: float
    net_income: float
    assets: float
    liabilities: float
    cashflow: float

    revenue_growth: float
    net_margin: float
    operating_margin: float
    gross_margin: float

    roe: float
    roic: float

    debt_to_asset: float
    free_cashflow_margin: float

    data_quality: float


class FinancialNormalizerV4:

    def normalize(
        self,
        financial,
    ):

        ticker = getattr(
            financial,
            "ticker",
            ""
        )

        revenue = self._number(
            financial,
            "revenue"
        )

        net_income = self._number(
            financial,
            "net_income"
        )

        assets = self._number(
            financial,
            "assets"
        )

        liabilities = self._number(
            financial,
            "liabilities"
        )

        cashflow = self._number(
            financial,
            "cashflow"
        )

        revenue_growth = self._number(
            financial,
            "revenue_growth"
        )

        gross_margin = self._number(
            financial,
            "gross_margin"
        )

        operating_margin = self._number(
            financial,
            "operating_margin"
        )

        roe = self._number(
            financial,
            "roe"
        )

        roic = self._number(
            financial,
            "roic"
        )

        net_margin = 0.0

        if revenue > 0:

            net_margin = (
                net_income / revenue
            )

        debt_to_asset = 0.0

        if assets > 0:

            debt_to_asset = (
                liabilities / assets
            )

        free_cashflow_margin = 0.0

        if revenue > 0:

            free_cashflow_margin = (
                cashflow / revenue
            )

        populated = 0

        fields = [
            revenue,
            net_income,
            assets,
            liabilities,
            cashflow,
        ]

        for value in fields:

            if value != 0:

                populated += 1

        data_quality = (
            populated / len(fields)
        ) * 100

        return NormalizedFinancials(

            ticker=ticker,

            revenue=revenue,

            net_income=net_income,

            assets=assets,

            liabilities=liabilities,

            cashflow=cashflow,

            revenue_growth=revenue_growth,

            net_margin=net_margin,

            operating_margin=operating_margin,

            gross_margin=gross_margin,

            roe=roe,

            roic=roic,

            debt_to_asset=debt_to_asset,

            free_cashflow_margin=free_cashflow_margin,

            data_quality=round(
                data_quality,
                2
            ),

        )



    @staticmethod
    def _number(
        obj,
        field,
    ):

        value = getattr(
            obj,
            field,
            0
        )

        if value is None:

            return 0.0

        try:

            return float(value)

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

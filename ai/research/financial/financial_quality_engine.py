from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FinancialQuality:

    ticker: str

    growth_score: float
    profitability_score: float
    balance_score: float
    cash_score: float
    consistency_score: float

    total_score: float

    reasons: list[str]


class FinancialQualityEngine:

    def analyze(
        self,
        financial
    ):

        reasons = []

        growth_score = 0
        profitability_score = 0
        balance_score = 0
        cash_score = 0
        consistency_score = 0

        revenue_growth = getattr(
            financial,
            "revenue_growth",
            0
        )

        net_margin = getattr(
            financial,
            "net_margin",
            0
        )

        operating_margin = getattr(
            financial,
            "operating_margin",
            0
        )

        gross_margin = getattr(
            financial,
            "gross_margin",
            0
        )

        roe = getattr(
            financial,
            "roe",
            0
        )

        roic = getattr(
            financial,
            "roic",
            0
        )

        debt_to_asset = getattr(
            financial,
            "debt_to_asset",
            0
        )

        free_cashflow_margin = getattr(
            financial,
            "free_cashflow_margin",
            0
        )

        revenue = getattr(
            financial,
            "revenue",
            0
        )

        income = getattr(
            financial,
            "net_income",
            0
        )

        assets = getattr(
            financial,
            "assets",
            0
        )

        liabilities = getattr(
            financial,
            "liabilities",
            0
        )

        cashflow = getattr(
            financial,
            "cashflow",
            0
        )



        # =========================================================
        # GROWTH — 20 POINTS
        # =========================================================

        if revenue_growth >= 0.20:

            growth_score = 20

            reasons.append(
                "Strong revenue growth"
            )

        elif revenue_growth >= 0.10:

            growth_score = 15

            reasons.append(
                "Healthy revenue growth"
            )

        elif revenue_growth > 0:

            growth_score = 8

            reasons.append(
                "Positive revenue growth"
            )

        elif revenue > 0:

            growth_score = 5

            reasons.append(
                "Positive revenue base"
            )



        # =========================================================
        # PROFITABILITY — 25 POINTS
        # =========================================================

        if (
            net_margin >= 0.20
            or operating_margin >= 0.25
        ):

            profitability_score = 25

            reasons.append(
                "Excellent profitability"
            )

        elif (
            net_margin >= 0.10
            or operating_margin >= 0.15
        ):

            profitability_score = 18

            reasons.append(
                "Strong profitability"
            )

        elif net_margin > 0:

            profitability_score = 10

            reasons.append(
                "Positive profitability"
            )

        elif income < 0:

            profitability_score = 0

            reasons.append(
                "Negative earnings"
            )



        # =========================================================
        # BALANCE SHEET — 20 POINTS
        # =========================================================

        if assets > 0:

            if debt_to_asset < 0.30:

                balance_score = 20

                reasons.append(
                    "Very strong balance sheet"
                )

            elif debt_to_asset < 0.50:

                balance_score = 16

                reasons.append(
                    "Healthy balance sheet"
                )

            elif debt_to_asset < 0.70:

                balance_score = 10

            elif liabilities < assets:

                balance_score = 5

            else:

                balance_score = 0

                reasons.append(
                    "Balance sheet risk"
                )



        # =========================================================
        # CASH GENERATION — 20 POINTS
        # =========================================================

        if free_cashflow_margin >= 0.15:

            cash_score = 20

            reasons.append(
                "Excellent cash generation"
            )

        elif free_cashflow_margin >= 0.08:

            cash_score = 15

            reasons.append(
                "Strong cash generation"
            )

        elif free_cashflow_margin > 0:

            cash_score = 8

            reasons.append(
                "Positive cashflow"
            )

        elif cashflow > 0:

            cash_score = 5

            reasons.append(
                "Positive operating cashflow"
            )



        # =========================================================
        # CONSISTENCY / CAPITAL RETURNS — 15 POINTS
        # =========================================================

        if roic >= 0.15:

            consistency_score += 8

            reasons.append(
                "Strong ROIC"
            )

        elif roic >= 0.10:

            consistency_score += 5



        if roe >= 0.15:

            consistency_score += 7

            reasons.append(
                "Strong ROE"
            )

        elif roe >= 0.10:

            consistency_score += 4



        consistency_score = min(
            consistency_score,
            15
        )



        total = (

            growth_score

            +

            profitability_score

            +

            balance_score

            +

            cash_score

            +

            consistency_score

        )



        return FinancialQuality(

            ticker=getattr(
                financial,
                "ticker",
                ""
            ),

            growth_score=growth_score,

            profitability_score=profitability_score,

            balance_score=balance_score,

            cash_score=cash_score,

            consistency_score=consistency_score,

            total_score=min(
                round(total, 2),
                100
            ),

            reasons=reasons,

        )

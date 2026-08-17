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


        reasons=[]


        growth_score = 0
        profitability_score = 0
        balance_score = 0
        cash_score = 0
        consistency_score = 0



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



        # Growth

        if revenue > 0:

            growth_score = 25

            reasons.append(
                "Positive revenue base"
            )



        # Profitability

        if revenue > 0:

            margin = income / revenue


            if margin > 0.20:

                profitability_score = 25

                reasons.append(
                    "High profit margin"
                )


            elif margin > 0:

                profitability_score = 15



        # Balance sheet

        if assets > liabilities:

            ratio = liabilities / assets


            if ratio < 0.5:

                balance_score = 20

                reasons.append(
                    "Healthy balance sheet"
                )

            else:

                balance_score = 10



        # Cash quality

        if cashflow > 0:

            cash_score = 20

            reasons.append(
                "Positive operating cashflow"
            )



        # Consistency

        if income > 0:

            consistency_score = 10



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

            ticker=financial.ticker,

            growth_score=growth_score,

            profitability_score=profitability_score,

            balance_score=balance_score,

            cash_score=cash_score,

            consistency_score=consistency_score,

            total_score=min(
                total,
                100
            ),

            reasons=reasons,

        )

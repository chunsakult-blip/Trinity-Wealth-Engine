from __future__ import annotations

from dataclasses import dataclass

from ai.research.financial.metrics import FinancialMetrics


@dataclass
class FinancialQualityScore:

    total: float

    profitability: float
    cash_generation: float
    balance_sheet: float
    stability: float



class FinancialQualityEngine:


    def calculate(
        self,
        metrics: FinancialMetrics,
    ) -> FinancialQualityScore:


        profitability=0
        cash_generation=0
        balance_sheet=0
        stability=0


        # Profitability 40 points

        if metrics.net_margin is not None:

            if metrics.net_margin > 0.20:
                profitability += 20

            elif metrics.net_margin > 0.10:
                profitability += 10



        if metrics.roe is not None:

            if metrics.roe > 0.20:
                profitability += 20

            elif metrics.roe > 0.10:
                profitability += 10



        # Cash generation 20

        if metrics.fcf_margin is not None:

            if metrics.fcf_margin > 0.15:
                cash_generation += 20

            elif metrics.fcf_margin > 0:
                cash_generation += 10



        # Balance sheet 20

        if metrics.debt_to_equity is not None:

            if metrics.debt_to_equity < 0.5:
                balance_sheet += 20

            elif metrics.debt_to_equity < 1:
                balance_sheet += 10



        # Stability 20

        if metrics.operating_margin is not None:

            if metrics.operating_margin > 0.25:
                stability += 20

            elif metrics.operating_margin > 0.10:
                stability += 10



        total = (
            profitability
            + cash_generation
            + balance_sheet
            + stability
        )


        return FinancialQualityScore(

            total=total,

            profitability=profitability,

            cash_generation=cash_generation,

            balance_sheet=balance_sheet,

            stability=stability,

        )

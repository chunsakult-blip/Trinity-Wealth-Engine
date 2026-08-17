from __future__ import annotations

import json
from datetime import datetime



class InvestmentReportGenerator:


    def generate(
        self,
        stocks
    ):

        report=[]


        for stock in stocks:

            report.append({

                "ticker":
                    stock.ticker,

                "name":
                    stock.name,

                "score":
                    stock.final_score,

                "rating":
                    stock.rating,

                "growth":
                    stock.growth_score,

                "financial":
                    stock.financial_score,

                "investor":
                    stock.investor_score,

                "reasons":
                    stock.reasons

            })


        return {

            "generated":
                datetime.now()
                .isoformat(),

            "total":
                len(report),

            "stocks":
                report

        }



    def save(
        self,
        data,
        path="data/investment_report.json"
    ):


        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2
            )


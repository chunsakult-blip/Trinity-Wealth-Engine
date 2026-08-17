from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InvestmentDecision:

    ticker: str

    decision: str

    confidence: float

    risk_level: str

    strengths: list[str]

    weaknesses: list[str]

    score: float



class InvestmentDecisionEngine:


    def analyze(
        self,
        stock
    ):

        score = stock.final_score

        strengths = []

        weaknesses = []


        if stock.growth_score >= 70:

            strengths.append(
                "Strong growth profile"
            )

        else:

            weaknesses.append(
                "Limited growth signal"
            )


        if stock.financial_score >= 70:

            strengths.append(
                "High financial quality"
            )

        else:

            weaknesses.append(
                "Financial quality below target"
            )


        if stock.investor_score >= 50:

            strengths.append(
                "Institutional ownership support"
            )


        if stock.valuation_score >= 80:

            strengths.append(
                "Attractive valuation"
            )

        else:

            weaknesses.append(
                "Valuation not cheap"
            )


        if score >= 85:

            decision = "BUY"

        elif score >= 70:

            decision = "ACCUMULATE"

        elif score >= 55:

            decision = "WATCH"

        else:

            decision = "PASS"



        if score >= 80:

            risk = "LOW"

        elif score >= 60:

            risk = "MEDIUM"

        else:

            risk = "HIGH"



        confidence = min(
            round(score * 0.9,2),
            95
        )


        return InvestmentDecision(

            ticker=stock.ticker,

            decision=decision,

            confidence=confidence,

            risk_level=risk,

            strengths=strengths,

            weaknesses=weaknesses,

            score=score,

        )


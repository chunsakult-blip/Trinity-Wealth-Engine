from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskScore:

    ticker: str
    risk_score: float
    level: str
    reasons: list[str]



class RiskEngine:


    def analyze(
        self,
        financial
    ):

        score = 100
        reasons = []


        if financial.net_income <= 0:

            score -= 30
            reasons.append(
                "Negative earnings"
            )


        if financial.cashflow <= 0:

            score -= 30
            reasons.append(
                "Weak operating cashflow"
            )


        if financial.liabilities > financial.assets:

            score -= 40
            reasons.append(
                "Balance sheet risk"
            )


        score = max(score,0)


        if score >= 80:

            level = "LOW"

        elif score >= 50:

            level = "MEDIUM"

        else:

            level = "HIGH"


        return RiskScore(

            ticker=financial.ticker,

            risk_score=score,

            level=level,

            reasons=reasons

        )

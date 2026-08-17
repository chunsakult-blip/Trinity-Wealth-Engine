from __future__ import annotations

from dataclasses import dataclass
from typing import Optional



@dataclass
class InvestorSignal:

    institutional_score: float
    insider_score: float
    momentum_score: float
    confidence_score: float

    total_score: float



class InvestorSignalEngine:


    def calculate(
        self,
        institutional_score: float = 0,
        insider_score: float = 0,
        momentum_score: float = 0,
    ) -> InvestorSignal:


        total = (
            institutional_score * 0.4
            +
            insider_score * 0.3
            +
            momentum_score * 0.3
        )


        return InvestorSignal(

            institutional_score=institutional_score,

            insider_score=insider_score,

            momentum_score=momentum_score,

            confidence_score=total,

            total_score=round(
                total,
                2
            ),

        )

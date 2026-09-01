from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RankedStock:

    ticker: str
    name: str

    growth_score: float
    financial_score: float
    investor_score: float

    total_score: float

    action: str


class MasterRanker:


    def calculate(
        self,
        candidate,
        financial: dict[str, Any],
        investor_score: float = 0,
    ) -> RankedStock:

        # --------------------------------------------------------
        # CANONICAL FINANCIAL CONTRACT
        #
        # FinancialIntelligenceEngine returns:
        #
        # {
        #     "status": "success",
        #     "metrics": {...},
        #     "quality": {
        #         "score": ...
        #     },
        #     ...
        # }
        # --------------------------------------------------------

        if not isinstance(financial, dict):

            raise TypeError(
                "MasterRanker expected canonical financial dict, "
                f"got {type(financial).__name__}."
            )


        quality_block = financial.get("quality")

        if not isinstance(quality_block, dict):

            raise TypeError(
                "MasterRanker expected financial['quality'] "
                "to be a dict."
            )


        quality = quality_block.get("score")

        if quality is None:

            raise ValueError(
                "MasterRanker expected financial['quality']['score']."
            )


        growth = getattr(
            candidate,
            "score",
            None,
        )

        if growth is None:

            raise ValueError(
                f"Candidate {getattr(candidate, 'ticker', '?')} "
                "has no score."
            )


        growth = float(growth)
        quality = float(quality)
        investor_score = float(investor_score)


        # --------------------------------------------------------
        # MASTER SCORE
        #
        # Growth       35%
        # Financial    45%
        # Investor     20%
        # --------------------------------------------------------

        total = (
            growth * 0.35
            +
            quality * 0.45
            +
            investor_score * 0.20
        )


        # --------------------------------------------------------
        # ACTION
        # --------------------------------------------------------

        if total >= 80:

            action = "STRONG BUY"

        elif total >= 65:

            action = "BUY"

        elif total >= 50:

            action = "WATCH"

        else:

            action = "PASS"


        return RankedStock(

            ticker=candidate.ticker,

            name=candidate.name,

            growth_score=growth,

            financial_score=quality,

            investor_score=investor_score,

            total_score=round(
                total,
                2,
            ),

            action=action,
        )


    def rank(
        self,
        stocks,
    ):

        return sorted(
            stocks,
            key=lambda x: x.total_score,
            reverse=True,
        )

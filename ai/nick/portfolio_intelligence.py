from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PortfolioCandidate:
    ticker: str
    score: float
    risk_score: float = 0.0
    conviction: float = 1.0


@dataclass(frozen=True)
class PortfolioPosition:
    ticker: str
    score: float
    risk_score: float
    allocation: float
    risk_level: str


@dataclass(frozen=True)
class PortfolioAllocation:
    positions: list[PortfolioPosition]
    cash_weight: float
    total_invested: float


class PortfolioIntelligence:
    """Deterministic portfolio allocator.

    Converts ranked candidates into a constrained portfolio without
    requiring an additional LLM call.
    """

    def __init__(
        self,
        *,
        max_position: float = 20.0,
        min_cash: float = 20.0,
        max_positions: int = 10,
    ) -> None:
        if max_position <= 0.0 or max_position > 100.0:
            raise ValueError("max_position must be within 0-100.")

        if min_cash < 0.0 or min_cash >= 100.0:
            raise ValueError("min_cash must be within 0-100.")

        if max_positions <= 0:
            raise ValueError("max_positions must be positive.")

        self.max_position = float(max_position)
        self.min_cash = float(min_cash)
        self.max_positions = int(max_positions)

    @staticmethod
    def _risk_level(risk_score: float) -> str:
        if risk_score >= 70.0:
            return "HIGH"
        if risk_score >= 40.0:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _effective_score(candidate: PortfolioCandidate) -> float:
        score = max(float(candidate.score), 0.0)
        risk = min(max(float(candidate.risk_score), 0.0), 100.0)
        conviction = min(max(float(candidate.conviction), 0.0), 1.0)

        # Penalize risk while preserving ranking quality.
        risk_multiplier = 1.0 - (risk * 0.50 / 100.0)

        return max(
            score * risk_multiplier * max(conviction, 0.25),
            0.0,
        )

    def allocate(
        self,
        candidates: list[PortfolioCandidate],
    ) -> PortfolioAllocation:
        if not candidates:
            return PortfolioAllocation(
                positions=[],
                cash_weight=100.0,
                total_invested=0.0,
            )

        ranked = sorted(
            candidates,
            key=self._effective_score,
            reverse=True,
        )[: self.max_positions]

        investable = max(
            100.0 - self.min_cash,
            0.0,
        )

        effective_scores = [
            self._effective_score(candidate)
            for candidate in ranked
        ]

        total_score = sum(effective_scores)

        if total_score <= 0.0:
            return PortfolioAllocation(
                positions=[],
                cash_weight=100.0,
                total_invested=0.0,
            )

        # Iterative cap + redistribution.
        active = list(range(len(ranked)))
        final_weights = [0.0] * len(ranked)
        remaining = investable

        while active:
            active_score = sum(
                effective_scores[index]
                for index in active
            )

            if active_score <= 0.0:
                break

            capped_any = False
            next_active: list[int] = []

            for index in active:
                proposed = (
                    remaining
                    * effective_scores[index]
                    / active_score
                )

                if proposed > self.max_position:
                    final_weights[index] = self.max_position
                    remaining -= self.max_position
                    capped_any = True
                else:
                    next_active.append(index)

            if not capped_any:
                for index in next_active:
                    proposed = (
                        remaining
                        * effective_scores[index]
                        / sum(
                            effective_scores[item]
                            for item in next_active
                        )
                    )
                    final_weights[index] = proposed
                remaining = 0.0
                break

            active = next_active

        rounded_weights = [
            round(weight, 2)
            for weight in final_weights
        ]

        # Correct rounding drift while preserving the max-position cap.
        rounded_total = round(sum(rounded_weights), 2)
        residual = round(investable - rounded_total, 2)

        if rounded_weights and residual != 0.0:
            order = sorted(
                range(len(rounded_weights)),
                key=lambda index: rounded_weights[index],
                reverse=True,
            )

            for index in order:
                if residual > 0.0:
                    room = round(
                        self.max_position - rounded_weights[index],
                        2,
                    )
                    adjustment = min(
                        residual,
                        max(room, 0.0),
                    )

                    if adjustment <= 0.0:
                        continue

                    rounded_weights[index] = round(
                        rounded_weights[index] + adjustment,
                        2,
                    )
                    residual = round(
                        residual - adjustment,
                        2,
                    )

                else:
                    if rounded_weights[index] >= self.max_position:
                        continue

                    removable = min(
                        -residual,
                        max(rounded_weights[index], 0.0),
                    )

                    if removable <= 0.0:
                        continue

                    rounded_weights[index] = round(
                        rounded_weights[index] - removable,
                        2,
                    )
                    residual = round(
                        residual + removable,
                        2,
                    )

                if residual == 0.0:
                    break

        positions = [
            PortfolioPosition(
                ticker=candidate.ticker.upper(),
                score=float(candidate.score),
                risk_score=float(candidate.risk_score),
                allocation=rounded_weights[index],
                risk_level=self._risk_level(
                    candidate.risk_score
                ),
            )
            for index, candidate in enumerate(ranked)
            if rounded_weights[index] > 0.0
        ]

        total_invested = round(
            sum(position.allocation for position in positions),
            2,
        )

        cash_weight = round(
            100.0 - total_invested,
            2,
        )

        return PortfolioAllocation(
            positions=positions,
            cash_weight=cash_weight,
            total_invested=total_invested,
        )


__all__ = [
    "PortfolioCandidate",
    "PortfolioPosition",
    "PortfolioAllocation",
    "PortfolioIntelligence",
]

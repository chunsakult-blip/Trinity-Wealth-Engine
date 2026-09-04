from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RebalanceInstruction:
    ticker: str
    action: str
    current_weight: float
    target_weight: float
    delta_weight: float


@dataclass(frozen=True)
class RebalancePlan:
    status: str
    actions: list[RebalanceInstruction]
    total_buy_weight: float
    total_sell_weight: float
    unchanged_count: int


class PortfolioRebalanceEngine:
    """
    Deterministic target-vs-current portfolio rebalance planner.

    O(n + m)
    No LLM
    No external I/O
    Does not expose current holdings to NICK.
    """

    def build_plan(
        self,
        target_portfolio: dict[str, Any],
        current_portfolio: dict[str, Any] | None,
        *,
        min_delta: float = 1.0,
    ) -> RebalancePlan:
        if not current_portfolio:
            return RebalancePlan(
                status="no_current_portfolio",
                actions=[],
                total_buy_weight=0.0,
                total_sell_weight=0.0,
                unchanged_count=0,
            )

        target_positions = target_portfolio.get("positions") or []
        current_positions = current_portfolio.get("positions") or []

        target_map: dict[str, float] = {}
        current_map: dict[str, float] = {}

        for position in target_positions:
            ticker = str(position.get("ticker", "")).strip().upper()
            if not ticker:
                continue
            weight = float(position.get("allocation", 0.0) or 0.0)
            target_map[ticker] = max(weight, 0.0)

        for position in current_positions:
            ticker = str(position.get("ticker", "")).strip().upper()
            if not ticker:
                continue
            weight = float(position.get("allocation", 0.0) or 0.0)
            current_map[ticker] = max(weight, 0.0)

        tickers = set(target_map) | set(current_map)

        actions: list[RebalanceInstruction] = []
        total_buy = 0.0
        total_sell = 0.0
        unchanged = 0

        for ticker in sorted(tickers):
            current_weight = current_map.get(ticker, 0.0)
            target_weight = target_map.get(ticker, 0.0)
            delta = round(target_weight - current_weight, 2)

            if abs(delta) < min_delta:
                unchanged += 1
                continue

            if delta > 0.0:
                action = "BUY"
                total_buy += delta
            else:
                action = "SELL"
                total_sell += abs(delta)

            actions.append(
                RebalanceInstruction(
                    ticker=ticker,
                    action=action,
                    current_weight=round(current_weight, 2),
                    target_weight=round(target_weight, 2),
                    delta_weight=delta,
                )
            )

        actions.sort(
            key=lambda item: abs(item.delta_weight),
            reverse=True,
        )

        status = "rebalance_required" if actions else "balanced"

        return RebalancePlan(
            status=status,
            actions=actions,
            total_buy_weight=round(total_buy, 2),
            total_sell_weight=round(total_sell, 2),
            unchanged_count=unchanged,
        )

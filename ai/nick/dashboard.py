from __future__ import annotations

from typing import Any

from ai.nick.decision_contract import NickDecisionContract


class NickDashboard:
    """Summarizes Nick's weekly or quarterly portfolio decision into a dashboard representation."""

    def __init__(self, decision: NickDecisionContract) -> None:
        self.decision = decision

    def render(self) -> dict[str, Any]:
        self.decision.validate()

        positions = []
        for item in self.decision.positions:
            positions.append(
                {
                    "symbol": item.symbol,
                    "thesis": item.thesis,
                    "status": item.status,
                    "target_weight": item.target_weight,
                    "conviction": item.conviction,
                }
            )

        return {
            "trigger": self.decision.trigger,
            "benchmark": self.decision.benchmark,
            "cash_weight": self.decision.cash_weight,
            "portfolio_status": "active" if positions else "idle",
            "positions": positions,
            "notes": self.decision.notes,
        }

    def compare_to_spy(self, *, spy_return: float, nick_return: float) -> dict[str, Any]:
        if nick_return > spy_return:
            relative_signal = "outperforming"
        elif nick_return < spy_return:
            relative_signal = "underperforming"
        else:
            relative_signal = "neutral"

        return {
            "spy_return": spy_return,
            "nick_return": nick_return,
            "relative_signal": relative_signal,
            "delta": nick_return - spy_return,
        }

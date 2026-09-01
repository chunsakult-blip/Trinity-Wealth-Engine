from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class NickKillCondition:
    metric: str
    trigger: str
    action: str = "reduce_or_exit"


@dataclass
class NickPositionDecision:
    symbol: str
    thesis: str
    catalyst: str
    kill_conditions: list[NickKillCondition] = field(default_factory=list)
    target_weight: float = 0.0
    conviction: float = 0.0
    status: Literal["intact", "evolving", "invalidated", "no_trade"] = "intact"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "thesis": self.thesis,
            "catalyst": self.catalyst,
            "kill_conditions": [
                {
                    "metric": item.metric,
                    "trigger": item.trigger,
                    "action": item.action,
                }
                for item in self.kill_conditions
            ],
            "target_weight": self.target_weight,
            "conviction": self.conviction,
            "status": self.status,
        }


@dataclass
class NickDecisionContract:
    trigger: str
    benchmark: str = "SPY"
    cash_weight: float = 0.2
    positions: list[NickPositionDecision] = field(default_factory=list)
    notes: str = ""

    def validate(self) -> None:
        if not self.trigger:
            raise ValueError("Nick decision trigger is required.")

        if not isinstance(self.positions, list):
            raise ValueError("Nick positions must be a list.")

        if self.cash_weight < 0.0 or self.cash_weight > 0.4:
            raise ValueError("Nick cash allocation must stay within the 0-40% policy ceiling.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "benchmark": self.benchmark,
            "cash_weight": self.cash_weight,
            "positions": [item.to_dict() for item in self.positions],
            "notes": self.notes,
        }

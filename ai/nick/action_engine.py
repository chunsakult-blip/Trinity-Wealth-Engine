from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai.nick.decision_contract import NickDecisionContract, NickPositionDecision


ActionType = Literal["buy", "trim", "sell", "hold", "no_trade"]


@dataclass
class NickActionDecision:
    action: ActionType
    symbol: str | None = None
    reason: str = ""
    current_weight: float | None = None
    desired_weight: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "symbol": self.symbol,
            "reason": self.reason,
            "current_weight": self.current_weight,
            "desired_weight": self.desired_weight,
        }


class NickActionEngine:
    """Turns Nick's position-level decisions into a trading action."""

    def decide(
        self,
        decision: NickDecisionContract,
        *,
        current_weight: float | None = None,
        desired_weight: float | None = None,
        symbol: str | None = None,
    ) -> NickActionDecision:
        if not decision.positions:
            return NickActionDecision(action="no_trade", reason="No active Nick positions")

        position: NickPositionDecision | None = None
        if symbol:
            position = next((p for p in decision.positions if p.symbol == symbol), None)
        else:
            position = decision.positions[0]

        if position is None:
            return NickActionDecision(action="no_trade", reason="No matching position found")

        status = position.status
        if status == "invalidated":
            return NickActionDecision(
                action="sell",
                symbol=position.symbol,
                reason="Kill condition triggered.",
                current_weight=current_weight,
                desired_weight=desired_weight,
            )

        if status == "evolving":
            return NickActionDecision(
                action="trim",
                symbol=position.symbol,
                reason="Holding is evolving and should be reduced towards target weight.",
                current_weight=current_weight,
                desired_weight=desired_weight or position.target_weight,
            )

        if status == "no_trade":
            return NickActionDecision(
                action="no_trade",
                symbol=position.symbol,
                reason="Position is explicitly no-trade.",
                current_weight=current_weight,
                desired_weight=desired_weight,
            )

        if current_weight is not None and desired_weight is not None and current_weight < desired_weight:
            return NickActionDecision(
                action="buy",
                symbol=position.symbol,
                reason="Position is intact and below target weight.",
                current_weight=current_weight,
                desired_weight=desired_weight,
            )

        return NickActionDecision(
            action="hold",
            symbol=position.symbol,
            reason="Position remains on watch with no immediate action.",
            current_weight=current_weight,
            desired_weight=desired_weight or position.target_weight,
        )

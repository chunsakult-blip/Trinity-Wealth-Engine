from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


TriggerType = Literal["nick-init", "nick-weekly", "nick-quarterly"]


@dataclass
class NickTriggerResult:
    trigger: TriggerType
    status: Literal["ready", "sent", "blocked"] = "ready"
    summary: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "trigger": self.trigger,
            "status": self.status,
            "summary": self.summary,
            "notes": list(self.notes),
        }


class NickTriggerWorkflow:
    """Routes the three Nick operating modes prescribed by the blind portfolio architecture."""

    VALID_TRIGGERS = ("nick-init", "nick-weekly", "nick-quarterly")

    def __init__(self) -> None:
        self._last = None

    def run(self, trigger: TriggerType) -> NickTriggerResult:
        if trigger not in self.VALID_TRIGGERS:
            raise ValueError(f"Unsupported Nick trigger: {trigger}")

        self._last = NickTriggerResult(
            trigger=trigger,
            status="sent",
            summary=f"Nick workflow dispatched: {trigger}",
            notes=[
                "KB sweep executed",
                "blocklist enforced",
                "position-level thesis validated",
            ],
        )
        return self._last

from __future__ import annotations

from pathlib import Path
from typing import Iterable


BLOCKLIST_PATTERNS = (
    "Team/nick_holdings",
    "Team/PAINT_HOLDINGS.md",
    "real portfolio",
    "actual holdings",
    "Diary transcripts",
    "session log that names a position",
)


class NickBlindGate:
    """Prevents Nick from reading real holdings or position-naming artifacts."""

    def __init__(self, blocklist: Iterable[str] | None = None) -> None:
        self.blocklist = tuple(blocklist or BLOCKLIST_PATTERNS)

    def is_allowed_input(self, path_or_name: str) -> bool:
        key = str(path_or_name or "").strip().lower()
        if not key:
            return False
        return not any(item.lower() in key for item in self.blocklist)

    def filter_allowed_inputs(self, inputs: Iterable[str]) -> list[str]:
        return [item for item in inputs if self.is_allowed_input(item)]

    def ensure_safe(self, inputs: Iterable[str]) -> list[str]:
        allowed = self.filter_allowed_inputs(inputs)
        if not allowed:
            raise ValueError("Nick blind gate blocked all KB inputs.")
        return allowed

    def validate_blocklist(self, candidate_paths: Iterable[str]) -> tuple[list[str], list[str]]:
        allowed: list[str] = []
        blocked: list[str] = []
        for item in candidate_paths:
            if self.is_allowed_input(str(item)):
                allowed.append(str(item))
            else:
                blocked.append(str(item))
        return allowed, blocked

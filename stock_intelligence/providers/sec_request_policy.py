from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Optional


class SECRequestPolicyError(ValueError):
    """Raised when an SEC request violates local request policy."""


@dataclass(frozen=True)
class SECRequestPolicy:
    """
    Local safety policy for SEC public-data requests.

    SEC guidance currently asks automated clients to identify themselves
    with a descriptive User-Agent and to moderate request volume.
    """

    min_interval_seconds: float = 0.12
    timeout_seconds: float = 20.0
    max_retries: int = 2

    def validate_user_agent(self, user_agent: Optional[str]) -> str:
        if user_agent is None:
            raise SECRequestPolicyError(
                "SEC User-Agent is required"
            )

        value = user_agent.strip()

        if not value:
            raise SECRequestPolicyError(
                "SEC User-Agent cannot be empty"
            )

        if len(value) < 8:
            raise SECRequestPolicyError(
                "SEC User-Agent is too short"
            )

        return value

    def validate_timeout(self) -> float:
        if self.timeout_seconds <= 0:
            raise SECRequestPolicyError(
                "timeout_seconds must be > 0"
            )

        return float(self.timeout_seconds)

    def validate_retries(self) -> int:
        if self.max_retries < 0:
            raise SECRequestPolicyError(
                "max_retries must be >= 0"
            )

        return int(self.max_retries)

    def validate_interval(self) -> float:
        if self.min_interval_seconds < 0:
            raise SECRequestPolicyError(
                "min_interval_seconds must be >= 0"
            )

        return float(self.min_interval_seconds)


class SECRequestRateGuard:
    """
    Process-local pacing guard.

    This does not attempt to model SEC server-side state.
    It simply prevents this process from issuing requests too quickly.
    """

    def __init__(
        self,
        min_interval_seconds: float = 0.12,
    ) -> None:

        if min_interval_seconds < 0:
            raise ValueError(
                "min_interval_seconds must be >= 0"
            )

        self.min_interval_seconds = float(
            min_interval_seconds
        )

        self._last_request_at: Optional[float] = None

    def wait_if_required(self) -> None:
        """
        Sleep only when the local process made a request too recently.
        """

        if self._last_request_at is None:
            return

        elapsed = monotonic() - self._last_request_at

        remaining = (
            self.min_interval_seconds
            - elapsed
        )

        if remaining > 0:
            from time import sleep

            sleep(remaining)

    def mark_request(self) -> None:
        self._last_request_at = monotonic()

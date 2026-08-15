from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional


class SECPeriodResolver:
    """
    Offline SEC Company Facts period resolver.

    Converts SEC fact observations into deterministic
    fiscal-period records.

    No network activity.
    """

    @staticmethod
    def _date(value: Any) -> Optional[date]:

        if value is None:
            return None

        try:
            return date.fromisoformat(
                str(value)
            )
        except ValueError:
            return None

    @staticmethod
    def fiscal_period(
        observation: Mapping[str, Any],
    ) -> Optional[str]:

        fy = observation.get("fy")

        if fy is None:
            return None

        fp = observation.get("fp")

        if fp:
            return f"FY{fy}-{fp}"

        return f"FY{fy}"

    @staticmethod
    def is_annual(
        observation: Mapping[str, Any],
    ) -> bool:

        form = str(
            observation.get(
                "form",
                "",
            )
        ).upper()

        fp = str(
            observation.get(
                "fp",
                "",
            )
        ).upper()

        return (
            form == "10-K"
            or fp == "FY"
        )

    @staticmethod
    def observation_date(
        observation: Mapping[str, Any],
    ) -> Optional[date]:

        for key in (
            "filed",
            "end",
            "start",
        ):

            parsed = SECPeriodResolver._date(
                observation.get(key)
            )

            if parsed is not None:
                return parsed

        return None

    @staticmethod
    def select_latest(
        observations: list[Mapping[str, Any]],
    ) -> Optional[Mapping[str, Any]]:

        valid = [
            item
            for item in observations
            if SECPeriodResolver.observation_date(
                item
            ) is not None
        ]

        if not valid:
            return None

        return max(
            valid,
            key=lambda item:
                SECPeriodResolver.observation_date(
                    item
                ),
        )

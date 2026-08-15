from __future__ import annotations

from typing import Any, Mapping, Optional


class SECUnitResolver:
    """
    Deterministic SEC Company Facts unit resolver.
    """

    SUPPORTED_UNITS = {
        "USD",
        "USD/shares",
        "shares",
    }

    @staticmethod
    def unit(
        observation: Mapping[str, Any],
    ) -> Optional[str]:

        unit = observation.get("unit")

        if unit is None:
            return None

        return str(unit)

    @classmethod
    def supported(
        cls,
        observation: Mapping[str, Any],
    ) -> bool:

        unit = cls.unit(observation)

        if unit is None:
            return False

        return unit in cls.SUPPORTED_UNITS

    @staticmethod
    def normalize_value(
        observation: Mapping[str, Any],
    ) -> Optional[float]:

        value = observation.get("val")

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return None

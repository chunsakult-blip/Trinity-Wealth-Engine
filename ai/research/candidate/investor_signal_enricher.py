from __future__ import annotations

import inspect
from typing import Any

from ai.research.investor.investor_seed_registry import (
    InvestorSeedRegistry,
)


class InvestorSignalEnricher:
    """
    Adapter between InvestorSeedRegistry and the candidate pipeline.

    The enricher does not invent investor intelligence.

    It consumes investor-derived signals already stored in
    InvestorSeedRegistry and exposes a normalized:

        investor_signal_score

    in the range 0.0 - 1.0.

    The original registry contract is:

        signals_for(ticker) -> list[dict[str, Any]]
    """

    def __init__(
        self,
        registry: InvestorSeedRegistry | None = None,
    ) -> None:
        self.registry = (
            registry
            if registry is not None
            else InvestorSeedRegistry()
        )

    def enrich(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Enrich a candidate record with investor-derived signals.

        The input record is copied rather than mutated.
        """

        item = dict(record)

        ticker = str(
            item.get("ticker") or ""
        ).strip().upper()

        if not ticker:
            item["investor_signal_score"] = 0.0
            item["investor_intelligence_status"] = (
                "missing_ticker"
            )
            item["investor_signal_evidence"] = []
            return item

        try:
            raw = self.registry.signals_for(ticker)
        except Exception as exc:
            item["investor_signal_score"] = 0.0
            item["investor_intelligence_status"] = "error"
            item["investor_intelligence_error"] = str(exc)
            item["investor_signal_evidence"] = []
            return item

        score, evidence = self._normalize(raw)

        item["investor_signal_score"] = score
        item["investor_intelligence_status"] = (
            "success" if evidence else "no_signal"
        )
        item["investor_signal_evidence"] = evidence

        return item

    @classmethod
    def _normalize(
        cls,
        raw: Any,
    ) -> tuple[float, list[Any]]:
        """
        Normalize registry output into:

            (score, evidence)

        InvestorSeedRegistry currently returns a list of dictionaries.
        This method remains defensive so the adapter can tolerate
        scalar, dictionary, or sequence payloads during integration.
        """

        if raw is None:
            return 0.0, []

        if isinstance(raw, dict):
            evidence = [raw]

            score = cls._score_from_mapping(raw)

            return cls._normalize_score(score), evidence

        if isinstance(raw, (list, tuple, set)):
            values = list(raw)

            if not values:
                return 0.0, []

            numeric_scores: list[float] = []

            for value in values:
                if isinstance(value, dict):
                    score = cls._score_from_mapping(value)

                    if score is not None:
                        numeric_scores.append(score)

                    continue

                number = cls._try_float(value)

                if number is not None:
                    numeric_scores.append(number)

            if numeric_scores:
                return (
                    cls._normalize_score(
                        max(numeric_scores)
                    ),
                    values,
                )

            return 0.0, values

        number = cls._try_float(raw)

        if number is not None:
            return (
                cls._normalize_score(number),
                [raw],
            )

        return 0.0, [raw]

    @classmethod
    def _score_from_mapping(
        cls,
        mapping: dict[str, Any],
    ) -> float | None:
        """
        Extract the strongest recognized score from an investor
        signal mapping.

        Registry records normally contain `confidence`, which is
        therefore included explicitly.
        """

        for key in (
            "investor_signal_score",
            "signal_score",
            "score",
            "strength",
            "confidence",
        ):
            if key not in mapping:
                continue

            number = cls._try_float(
                mapping.get(key)
            )

            if number is not None:
                return number

        return None

    @staticmethod
    def _try_float(
        value: Any,
    ) -> float | None:
        try:
            number = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if number != number:
            return None

        return number

    @classmethod
    def _normalize_score(
        cls,
        value: float,
    ) -> float:
        """
        Convert scores into the canonical 0.0 - 1.0 range.

        Values greater than 1 are interpreted as percentages.
        """

        if value > 1.0:
            value = value / 100.0

        return round(
            max(
                0.0,
                min(value, 1.0),
            ),
            4,
        )


def inspect_registry_contract() -> None:
    """
    Diagnostic helper used during integration testing.
    """

    signature = inspect.signature(
        InvestorSeedRegistry.signals_for
    )

    print(
        "InvestorSeedRegistry.signals_for:",
        signature,
    )

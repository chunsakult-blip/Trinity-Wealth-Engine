from __future__ import annotations

from typing import Any


class CandidateRanker:
    """
    Deterministic candidate ranking foundation.

    Security Master classification is eligibility information,
    NOT investment alpha.

    Investment signals are added downstream.
    """

    def score(
        self,
        record: dict[str, Any],
    ) -> float:

        score = 0.0

        investor_signal = self._safe_float(
            record.get("investor_signal_score")
        )

        universe_signal = self._safe_float(
            record.get("universe_signal_score")
        )

        financial_signal = self._safe_float(
            record.get("financial_signal_score")
        )

        earnings_signal = self._safe_float(
            record.get("earnings_signal_score")
        )

        valuation_signal = self._safe_float(
            record.get("valuation_signal_score")
        )

        score += investor_signal * 35.0
        score += universe_signal * 5.0
        score += financial_signal * 25.0
        score += earnings_signal * 15.0
        score += valuation_signal * 20.0

        return round(
            max(
                0.0,
                min(score, 100.0),
            ),
            4,
        )

    def rank(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        ranked: list[dict[str, Any]] = []

        for record in records:

            item = dict(record)

            item["candidate_score"] = self.score(item)

            item["research_priority"] = (
                item["candidate_score"]
            )

            ranked.append(item)

        ranked.sort(
            key=lambda item: (
                float(
                    item.get(
                        "candidate_score",
                        0.0,
                    )
                    or 0.0
                ),
                str(
                    item.get(
                        "ticker",
                        "",
                    )
                ),
            ),
            reverse=True,
        )

        return ranked

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float:

        try:
            result = float(value or 0.0)

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

        if result != result:
            return 0.0

        return max(
            0.0,
            min(result, 1.0),
        )

from typing import Any


class CandidateSignalAdapter:
    SIGNAL_FIELDS = (
        "investor_signal_score",
        "universe_signal_score",
        "financial_signal_score",
        "earnings_signal_score",
        "valuation_signal_score",
    )

    def enrich(self, record: dict[str, Any]) -> dict[str, Any]:
        item = dict(record)

        for field in self.SIGNAL_FIELDS:
            item[field] = self._normalize(item.get(field))

        return item

    def enrich_many(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.enrich(record) for record in records]

    @staticmethod
    def _normalize(value: Any) -> float:
        try:
            number = float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

        if number != number:
            return 0.0

        return max(0.0, min(number, 1.0))

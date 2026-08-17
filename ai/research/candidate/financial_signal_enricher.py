from typing import Any


class FinancialSignalEnricher:
    """
    Converts SEC financial intelligence into a normalized
    financial candidate signal.
    """

    def enrich(self, record: dict[str, Any]) -> dict[str, Any]:
        item = dict(record)

        cik = item.get("cik")

        if not cik:
            item["financial_signal_score"] = 0.0
            item["financial_intelligence_status"] = "missing_cik"
            return item

        try:
            cik_value = int(cik)
        except (TypeError, ValueError):
            item["financial_signal_score"] = 0.0
            item["financial_intelligence_status"] = "invalid_cik"
            return item

        try:
            from ai.research.financial.engine import FinancialIntelligenceEngine

            engine = FinancialIntelligenceEngine()

            result = engine.analyze_company(
                cik_value,
                ticker=item.get("ticker"),
                company_name=item.get("company_name"),
            )

        except Exception as exc:
            item["financial_signal_score"] = 0.0
            item["financial_intelligence_status"] = "error"
            item["financial_intelligence_error"] = str(exc)
            return item

        if result.get("status") != "success":
            item["financial_signal_score"] = 0.0
            item["financial_intelligence_status"] = "failed"
            return item

        quality = result.get("quality") or {}

        raw_score = quality.get("score") or 0.0

        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.0

        if score != score:
            score = 0.0

        if score > 1.0:
            score = score / 100.0

        score = max(0.0, min(score, 1.0))

        item["financial_signal_score"] = score
        item["financial_intelligence_status"] = "success"

        item["financial_quality_score"] = self.number(quality.get("score"))
        item["financial_completeness"] = self.number(quality.get("completeness"))
        item["financial_freshness"] = self.number(quality.get("freshness"))
        item["financial_consistency"] = self.number(quality.get("consistency"))
        item["financial_confidence"] = str(quality.get("confidence") or "")
        item["financial_warnings"] = list(quality.get("warnings") or [])

        item["financial_metrics"] = result.get("metrics") or {}
        item["financial_latest_period"] = result.get("latest_period")
        item["financial_prior_period"] = result.get("prior_period")
        item["financial_ttm"] = result.get("ttm")
        item["financial_period_count"] = int(result.get("period_count") or 0)
        item["financial_evidence"] = list(result.get("evidence") or [])

        return item

    def enrich_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.enrich(record) for record in records]

    def number(self, value: Any) -> float:
        try:
            number_value = float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

        if number_value != number_value:
            return 0.0

        return number_value

from __future__ import annotations

from typing import Any

from ai.research.candidate.candidate_ranker import CandidateRanker
from ai.research.candidate.candidate_store import CandidateStore
from ai.research.candidate.financial_signal_enricher import (
    FinancialSignalEnricher,
)
from ai.research.candidate.investor_signal_enricher import (
    InvestorSignalEnricher,
)


class CandidatePipeline:
    """
    Converts Security Master output into a persistent
    investment research candidate pool.

    Pipeline:

        Security Master
            -> Financial Enrichment
            -> Investor Enrichment
            -> Candidate Ranking
            -> Candidate Store
    """

    def __init__(
        self,
        store: CandidateStore | None = None,
        ranker: CandidateRanker | None = None,
        financial_enricher: FinancialSignalEnricher | None = None,
        investor_enricher: InvestorSignalEnricher | None = None,
    ) -> None:

        self.store = store or CandidateStore()
        self.ranker = ranker or CandidateRanker()

        self.financial_enricher = (
            financial_enricher
            or FinancialSignalEnricher()
        )

        self.investor_enricher = (
            investor_enricher
            or InvestorSignalEnricher()
        )

    def ingest(
        self,
        records: list[dict[str, Any]],
        *,
        top_n: int = 600,
    ) -> dict[str, Any]:

        investable = [
            record
            for record in records
            if record.get("investable_equity") is True
        ]

        enriched: list[dict[str, Any]] = []

        for record in investable:

            item = dict(record)

            # --------------------------------------------------------
            # FINANCIAL INTELLIGENCE
            # --------------------------------------------------------

            item = self.financial_enricher.enrich(item)

            # --------------------------------------------------------
            # INVESTOR INTELLIGENCE
            # --------------------------------------------------------

            item = self.investor_enricher.enrich(item)

            enriched.append(item)

        # ------------------------------------------------------------
        # RANK
        # ------------------------------------------------------------

        ranked = self.ranker.rank(enriched)

        selected = ranked[: max(1, int(top_n))]

        # ------------------------------------------------------------
        # PERSIST
        # ------------------------------------------------------------

        for record in selected:

            item = dict(record)

            item["research_status"] = "queued"

            self.store.upsert(item)

        return {
            "input_records": len(records),
            "investable_records": len(investable),
            "enriched_records": len(enriched),
            "ranked_records": len(ranked),
            "selected_candidates": len(selected),
            "top_n": top_n,
            "database_summary": self.store.summary(),
        }

    def top(
        self,
        limit: int = 600,
    ) -> list[dict[str, Any]]:

        return self.store.top(limit)

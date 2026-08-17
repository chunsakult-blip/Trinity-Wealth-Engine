from __future__ import annotations

from typing import Any

from ai.research.candidate.candidate_ranker import CandidateRanker
from ai.research.candidate.candidate_store import CandidateStore


class CandidatePipeline:
    """
    Converts Security Master output into a persistent
    investment research candidate pool.
    """

    def __init__(
        self,
        store: CandidateStore | None = None,
        ranker: CandidateRanker | None = None,
    ) -> None:
        self.store = store or CandidateStore()
        self.ranker = ranker or CandidateRanker()

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

        ranked = self.ranker.rank(investable)

        selected = ranked[: max(1, int(top_n))]

        for record in selected:
            item = dict(record)
            item["research_status"] = "queued"
            self.store.upsert(item)

        return {
            "input_records": len(records),
            "investable_records": len(investable),
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

"""
Research Orchestrator.

Executes registered research specialists and aggregates their
structured AgentResult outputs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ai.agent_result import AgentResult
from ai.research.request import ResearchRequest


ResearchWorker = Callable[[ResearchRequest], AgentResult]


class ResearchOrchestrator:

    name = "Research Orchestrator"

    def __init__(
        self,
        workers: Iterable[ResearchWorker] | None = None,
    ) -> None:
        self.workers = list(workers or [])

    def register(self, worker: ResearchWorker) -> None:
        if worker not in self.workers:
            self.workers.append(worker)

    def execute(self, request: ResearchRequest) -> AgentResult:

        results: list[AgentResult] = []
        warnings: list[str] = []

        for worker in self.workers:
            worker_name = getattr(
                worker,
                "__name__",
                worker.__class__.__name__,
            )

            try:
                result = worker(request)

                if not isinstance(result, AgentResult):
                    result = AgentResult(
                        agent=worker_name,
                        status="failure",
                        summary="Research worker returned an invalid result.",
                        warnings=["Worker must return AgentResult."],
                    )

            except Exception as exc:
                result = AgentResult(
                    agent=worker_name,
                    status="failure",
                    summary=f"{type(exc).__name__}: {exc}",
                    warnings=[str(exc)],
                )

            results.append(result)

            if result.failed():
                warnings.append(
                    f"{result.agent}: "
                    f"{result.summary or 'research worker failed'}"
                )

            warnings.extend(result.warnings)

        successful = [
            result for result in results
            if result.success()
        ]

        evidence: list[dict] = []

        for result in results:
            evidence.extend(result.evidence)

        combined_data = {
            "request": request.to_dict(),
            "worker_count": len(self.workers),
            "completed_workers": len(results),
            "successful_workers": len(successful),
            "worker_results": [
                result.to_dict()
                for result in results
            ],
            "research_data": [
                result.data
                for result in successful
            ],
        }

        if not self.workers:
            return AgentResult(
                agent=self.name,
                status="success",
                summary=(
                    "Research request accepted; "
                    "no specialists registered yet."
                ),
                data=combined_data,
                warnings=[
                    "No research specialists are registered."
                ],
            )

        if successful:
            status = "success"
            summary = (
                f"Research completed by "
                f"{len(successful)}/{len(results)} "
                "registered specialists."
            )
        else:
            status = "failure"
            summary = "All registered research specialists failed."

        return AgentResult(
            agent=self.name,
            status=status,
            summary=summary,
            data=combined_data,
            evidence=evidence,
            warnings=list(dict.fromkeys(warnings)),
        )

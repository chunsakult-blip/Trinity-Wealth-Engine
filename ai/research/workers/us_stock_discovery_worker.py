"""
ATLAS US Stock Discovery Research Worker.

Bridges the SEC universe-discovery Scout into the
ResearchOrchestrator contract and canonicalizes the
discovered securities through SecurityMaster V2.

Pipeline:

    USStockScout
        |
        v
    raw SEC universe
        |
        v
    SecurityMaster V2
        |
        +--> canonical securities
        |
        +--> investable universe
        |
        v
    AgentResult
"""

from __future__ import annotations

from typing import Any

from ai.agent_result import AgentResult
from ai.research.request import ResearchRequest
from ai.research.scout.us_stock_scout import USStockScout
from ai.research.security import SecurityMaster


class USStockDiscoveryWorker:

    name = "US Stock Discovery Worker"

    def __init__(
        self,
        scout: USStockScout | None = None,
        security_master: SecurityMaster | None = None,
    ) -> None:
        self.scout = scout or USStockScout()
        self.security_master = security_master or SecurityMaster()

    def __call__(
        self,
        request: ResearchRequest,
    ) -> AgentResult:

        # --------------------------------------------------------
        # 1. DISCOVERY
        # --------------------------------------------------------

        scout_result = self.scout.scan()

        if not isinstance(scout_result, AgentResult):
            return AgentResult(
                agent=self.name,
                status="failure",
                summary=(
                    "US Stock Scout returned an invalid result."
                ),
                warnings=[
                    "Scout must return AgentResult."
                ],
            )

        if scout_result.status != "success":
            return AgentResult(
                agent=self.name,
                status="failure",
                summary="US Stock Scout failed.",
                data={
                    "request": request.to_dict(),
                    "scout": scout_result.to_dict(),
                },
                evidence=list(scout_result.evidence),
                warnings=list(scout_result.warnings),
                confidence=scout_result.confidence,
            )

        discovery_data = scout_result.data

        raw_universe = discovery_data.get(
            "universe",
            [],
        )

        if not isinstance(raw_universe, list):
            return AgentResult(
                agent=self.name,
                status="failure",
                summary=(
                    "US Stock Scout returned an invalid "
                    "universe payload."
                ),
                data={
                    "request": request.to_dict(),
                    "discovery": discovery_data,
                },
                evidence=list(scout_result.evidence),
                warnings=[
                    "Scout discovery.universe must be a list."
                ],
                confidence=scout_result.confidence,
            )

        # --------------------------------------------------------
        # 2. SECURITY MASTER
        # --------------------------------------------------------

        try:
            security_records = self.security_master.build(
                raw_universe
            )

        except Exception as exc:
            return AgentResult(
                agent=self.name,
                status="failure",
                summary=(
                    "Security Master classification failed."
                ),
                data={
                    "request": request.to_dict(),
                    "discovery": discovery_data,
                    "security_master": {
                        "stage": "classification",
                        "input_count": len(raw_universe),
                    },
                },
                evidence=list(scout_result.evidence),
                warnings=[
                    (
                        "SecurityMaster failure: "
                        f"{type(exc).__name__}: {exc}"
                    )
                ],
                confidence=scout_result.confidence,
            )

        investable_records = (
            self.security_master.investable_only(
                security_records
            )
        )

        security_summary = (
            self.security_master.summarize(
                security_records
            )
        )

        # --------------------------------------------------------
        # 3. EVIDENCE
        # --------------------------------------------------------

        evidence: list[dict[str, Any]] = list(
            scout_result.evidence
        )

        evidence.append(
            {
                "type": "canonicalization",
                "source": "ATLAS_SECURITY_MASTER",
                "description": (
                    "SEC-discovered securities were "
                    "canonicalized and classified by "
                    "SecurityMaster V2."
                ),
            }
        )

        # --------------------------------------------------------
        # 4. WARNINGS
        # --------------------------------------------------------

        warnings = list(
            scout_result.warnings
        )

        if len(security_records) != len(raw_universe):
            warnings.append(
                (
                    "SecurityMaster skipped "
                    f"{len(raw_universe) - len(security_records)} "
                    "invalid discovery records."
                )
            )

        if not investable_records:
            warnings.append(
                "SecurityMaster produced zero investable securities."
            )

        # Preserve ordering while removing duplicates.
        warnings = list(
            dict.fromkeys(warnings)
        )

        # --------------------------------------------------------
        # 5. FINAL AGENT RESULT
        # --------------------------------------------------------

        return AgentResult(
            agent=self.name,
            status="success",
            summary=(
                "US equity universe discovery and "
                "Security Master canonicalization completed."
            ),
            data={
                "request": request.to_dict(),

                "market": "US",

                "discovery": {
                    "source_agent": scout_result.agent,
                    "source_status": scout_result.status,
                    "source": discovery_data.get(
                        "source"
                    ),
                    "source_url": discovery_data.get(
                        "source_url"
                    ),
                    "exchange_filter": discovery_data.get(
                        "exchange_filter",
                        [],
                    ),
                    "raw_count": len(raw_universe),
                    "raw_universe": raw_universe,
                    "exchange_counts": discovery_data.get(
                        "exchange_counts",
                        {},
                    ),
                    "elapsed_seconds": discovery_data.get(
                        "elapsed_seconds"
                    ),
                },

                "security_master": {
                    "stage": "canonicalization",
                    "count": len(security_records),
                    "records": security_records,
                    "summary": security_summary,
                },

                "investable_universe": {
                    "count": len(investable_records),
                    "records": investable_records,
                },

                "source_agent": scout_result.agent,
                "source_status": scout_result.status,
            },
            evidence=evidence,
            warnings=warnings,
            confidence=scout_result.confidence,
        )

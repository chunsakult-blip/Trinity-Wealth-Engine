"""
Evidence Collector.

Collects evidence from research agents before reasoning.
"""


class EvidenceCollector:

    name = "Evidence Collector"

    def collect(self, research_results: list[dict]) -> dict:
        return {
            "agent": self.name,
            "evidence_count": len(research_results),
            "evidence": research_results,
        }

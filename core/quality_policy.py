from typing import Dict, Any

QUALITY_POLICY = {
    "version": "1.0",
    "blockers": {
        "MISSING_STRUCTURE": {"bypassable": False},
        "NO_PROVENANCE_SOURCE": {"bypassable": False},
        "UNVERIFIED_ALL_SOURCES": {"bypassable": False},
        "MOCK_SOURCE": {"bypassable": False},
        "INGESTION_AS_PUBLISHED": {"bypassable": False},
        "INCOMPLETE_CANONICAL": {"bypassable": True},
        "EMPTY_EVIDENCE_LEDGER": {"bypassable": False},
        "INVALID_SOURCE_REFERENCE": {"bypassable": False},
        "UNVERIFIED_FACT": {"bypassable": True},
        "INVALID_CONSENSUS": {"bypassable": True},
        "CONFLICTING_METRICS": {"bypassable": False},
        "UNKNOWN_IDENTIFIER": {"bypassable": False},
        "NO_EVIDENCE_CITATION": {"bypassable": False},
        "MACRO_COVERAGE_FAILURE": {"bypassable": True},
        "FINANCIAL_COVERAGE_FAILURE": {"bypassable": True},
        "BAD_MATH": {"bypassable": False},
    },
    "caps": {
        "MISSING_PUBLICATION_DATE": {"limit": 70, "bypassable": True},
        "SINGLE_INDEPENDENT_SOURCE": {"limit": 85, "bypassable": True},
    },
    "warnings": {
        "UNVERIFIED_SOURCE_WARNING": {"bypassable": True},
    }
}

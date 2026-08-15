"""
Normalized research request contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResearchRequest:
    query: str
    tickers: list[str] = field(default_factory=list)
    research_type: str = "company"
    depth: str = "standard"
    requested_by: str = "Nick"

    def __post_init__(self) -> None:
        self.query = str(self.query).strip()

        self.tickers = list(
            dict.fromkeys(
                str(ticker).strip().upper()
                for ticker in self.tickers
                if str(ticker).strip()
            )
        )

        self.research_type = str(self.research_type).strip() or "company"
        self.depth = str(self.depth).strip() or "standard"
        self.requested_by = str(self.requested_by).strip() or "Nick"

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "tickers": list(self.tickers),
            "research_type": self.research_type,
            "depth": self.depth,
            "requested_by": self.requested_by,
        }

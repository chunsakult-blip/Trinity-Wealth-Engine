"""
Research request shared by the research division.
"""

from dataclasses import dataclass, field


@dataclass
class ResearchRequest:
    query: str
    tickers: list[str] = field(default_factory=list)
    research_type: str = "company"
    depth: str = "standard"
    requested_by: str = "Nick"

"""
Trinity v2 AI configuration.

This module intentionally contains architecture-level configuration only.
Provider-specific implementation will be connected later.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AIConfig:
    system_name: str = "TRINITY"
    version: str = "2.0"
    role: str = "AI Investment Operating System"

    chief_agent: str = "Nick"
    chief_role: str = "Chief Investment Officer"

    max_research_depth: int = 3
    require_evidence: bool = True
    require_verification: bool = True
    require_reflection: bool = True


DEFAULT_AI_CONFIG = AIConfig()

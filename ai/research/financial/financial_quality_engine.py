"""
LEGACY COMPATIBILITY SHIM.

Canonical financial quality ownership lives in:
    ai.research.financial.quality

Do not add scoring logic here.
"""

from __future__ import annotations

from .models import FinancialQuality
from .quality import FinancialQualityEngine

__all__ = [
    "FinancialQuality",
    "FinancialQualityEngine",
]

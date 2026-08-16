"""
ATLAS Financial Intelligence Layer.

Mega Batch E:
SEC facts -> normalized financial facts -> metrics -> quality.
"""

from .models import (
    FinancialFact,
    FinancialPeriod,
    NormalizedFinancials,
    FinancialQuality,
)

from .normalizer import FinancialFactNormalizer
from .metrics import FinancialMetricsEngine
from .quality import FinancialQualityEngine

__all__ = [
    "FinancialFact",
    "FinancialPeriod",
    "NormalizedFinancials",
    "FinancialQuality",
    "FinancialFactNormalizer",
    "FinancialMetricsEngine",
    "FinancialQualityEngine",
]

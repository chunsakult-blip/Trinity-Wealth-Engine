from __future__ import annotations

from typing import Any, Mapping, Optional

from .financial_model import (
    FinancialPeriod,
    NormalizedFinancials,
)
from .financial_normalization import (
    normalize_financial_period,
    normalize_financials,
)


class SECNormalizationBridge:
    """
    Canonical bridge between SEC raw financial records
    and the Nick V3 normalized financial model.

    IMPORTANT:
    This layer performs NO network activity.

    SEC network retrieval belongs exclusively to sec_adapter.py.

    Responsibilities:
        SEC raw record
            ->
        canonical raw financial mapping
            ->
        financial normalization
            ->
        provenance-preserving canonical model
    """

    SOURCE = "SEC"

    def normalize_period(
        self,
        ticker: str,
        fiscal_period: str,
        raw: Mapping[str, Any],
        *,
        source_url: Optional[str] = None,
        accession: Optional[str] = None,
        retrieved_at: Optional[str] = None,
    ) -> FinancialPeriod:

        return normalize_financial_period(
            ticker=ticker,
            fiscal_period=fiscal_period,
            raw=raw,
            source=self.SOURCE,
            source_url=source_url,
            accession=accession,
            retrieved_at=retrieved_at,
        )

    def normalize_dataset(
        self,
        ticker: str,
        raw_periods: list[Mapping[str, Any]],
    ) -> NormalizedFinancials:

        return normalize_financials(
            ticker=ticker,
            raw_periods=raw_periods,
            source=self.SOURCE,
        )


def normalize_sec_period(
    ticker: str,
    fiscal_period: str,
    raw: Mapping[str, Any],
    *,
    source_url: Optional[str] = None,
    accession: Optional[str] = None,
    retrieved_at: Optional[str] = None,
) -> FinancialPeriod:

    bridge = SECNormalizationBridge()

    return bridge.normalize_period(
        ticker=ticker,
        fiscal_period=fiscal_period,
        raw=raw,
        source_url=source_url,
        accession=accession,
        retrieved_at=retrieved_at,
    )


def normalize_sec_dataset(
    ticker: str,
    raw_periods: list[Mapping[str, Any]],
) -> NormalizedFinancials:

    bridge = SECNormalizationBridge()

    return bridge.normalize_dataset(
        ticker=ticker,
        raw_periods=raw_periods,
    )

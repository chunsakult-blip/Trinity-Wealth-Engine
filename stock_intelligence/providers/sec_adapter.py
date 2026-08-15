from __future__ import annotations

"""
NICK V3 — Canonical SEC Primary Fundamentals Adapter

Purpose
-------
Single production-facing adapter for SEC company fundamentals.

Design rules
------------
1. SEC is PRIMARY for fundamentals.
2. No API call occurs during module import.
3. Network access happens only through explicit fetch methods.
4. SEC User-Agent must come from environment configuration.
5. Raw SEC payload is preserved by caller if required.
6. Normalized records retain provenance.
7. Period identity is never inferred from dictionary position.
8. Latest filing wins only when explicitly requested by consumer.
"""

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SEC_DATA_BASE = "https://data.sec.gov"
SEC_SUBMISSIONS_BASE = "https://data.sec.gov/submissions"

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.15


# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------

class SECAdapterError(RuntimeError):
    """Base SEC adapter exception."""


class SECConfigurationError(SECAdapterError):
    """Raised when SEC runtime configuration is missing."""


class SECNetworkError(SECAdapterError):
    """Raised when SEC network access fails."""


class SECResponseError(SECAdapterError):
    """Raised when SEC returns an unexpected response."""


# ----------------------------------------------------------------------
# Provenance
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class SECProvenance:
    source: str
    source_url: str
    retrieved_at: str
    form: str | None
    filed: str | None
    accession_number: str | None
    cik: str


# ----------------------------------------------------------------------
# Normalized financial record
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class SECFinancialRecord:
    ticker: str | None
    cik: str
    concept: str
    label: str | None

    value: float | None
    unit: str

    fiscal_year: int | None
    fiscal_period: str | None
    frame: str | None

    start_date: str | None
    end_date: str | None

    form: str | None
    filed: str | None
    accession_number: str | None

    provenance: SECProvenance


# ----------------------------------------------------------------------
# Canonical SEC concept mapping
# ----------------------------------------------------------------------

CONCEPT_MAP: dict[str, tuple[str, ...]] = {
    "revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ),

    "cost_of_revenue": (
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
    ),

    "gross_profit": (
        "GrossProfit",
    ),

    "operating_income": (
        "OperatingIncomeLoss",
    ),

    "pretax_income": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ),

    "net_income": (
        "NetIncomeLoss",
        "ProfitLoss",
    ),

    "eps_basic": (
        "EarningsPerShareBasic",
    ),

    "eps_diluted": (
        "EarningsPerShareDiluted",
    ),

    "cash": (
        "CashAndCashEquivalentsAtCarryingValue",
    ),

    "short_term_investments": (
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
    ),

    "assets": (
        "Assets",
    ),

    "current_assets": (
        "AssetsCurrent",
    ),

    "liabilities": (
        "Liabilities",
    ),

    "current_liabilities": (
        "LiabilitiesCurrent",
    ),

    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),

    "debt": (
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ),

    "current_debt": (
        "LongTermDebtCurrent",
        "ShortTermBorrowings",
        "ShortTermDebt",
    ),

    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
    ),

    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
    ),

    "shares_outstanding": (
        "EntityCommonStockSharesOutstanding",
    ),
}


# ----------------------------------------------------------------------
# Adapter
# ----------------------------------------------------------------------

class SECAdapter:
    """
    Canonical production SEC adapter.

    Network calls are explicit:
        fetch_company_facts()
        fetch_submissions()

    No network call occurs during initialization.
    """

    provider_name = "sec"
    authority = "primary"
    domain = "fundamentals"

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
    ) -> None:

        self.timeout = float(timeout)
        self.min_request_interval = max(
            0.0,
            float(min_request_interval),
        )

        self.user_agent = (
            user_agent
            or os.getenv("SEC_USER_AGENT")
            or os.getenv("SEC_API_USER_AGENT")
            or os.getenv("USER_AGENT")
        )

        self._last_request_at = 0.0

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def validate_configuration(self) -> None:
        if not self.user_agent:
            raise SECConfigurationError(
                "SEC User-Agent is not configured. "
                "Set SEC_USER_AGENT in the environment."
            )

        if len(self.user_agent.strip()) < 5:
            raise SECConfigurationError(
                "SEC User-Agent is too short."
            )

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at

        if elapsed < self.min_request_interval:
            time.sleep(
                self.min_request_interval - elapsed
            )

    def _get_json(self, url: str) -> dict[str, Any]:

        self.validate_configuration()
        self._wait_for_rate_limit()

        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "data.sec.gov",
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:

                status = getattr(
                    response,
                    "status",
                    200,
                )

                if status != 200:
                    raise SECResponseError(
                        f"SEC returned HTTP {status}"
                    )

                payload = response.read()

        except HTTPError as exc:
            raise SECNetworkError(
                f"SEC HTTP error {exc.code}: {url}"
            ) from exc

        except URLError as exc:
            raise SECNetworkError(
                f"SEC network error: {exc.reason}"
            ) from exc

        except TimeoutError as exc:
            raise SECNetworkError(
                f"SEC request timed out: {url}"
            ) from exc

        finally:
            self._last_request_at = time.monotonic()

        try:
            return json.loads(
                payload.decode("utf-8")
            )

        except json.JSONDecodeError as exc:
            raise SECResponseError(
                "SEC response was not valid JSON."
            ) from exc

    # ------------------------------------------------------------------
    # SEC endpoints
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_cik(cik: str | int) -> str:

        digits = "".join(
            character
            for character in str(cik)
            if character.isdigit()
        )

        if not digits:
            raise ValueError(
                f"Invalid SEC CIK: {cik}"
            )

        return digits.zfill(10)

    def companyfacts_url(
        self,
        cik: str | int,
    ) -> str:

        normalized = self.normalize_cik(cik)

        return (
            f"{SEC_DATA_BASE}/api/xbrl/companyfacts/"
            f"CIK{normalized}.json"
        )

    def submissions_url(
        self,
        cik: str | int,
    ) -> str:

        normalized = self.normalize_cik(cik)

        return (
            f"{SEC_SUBMISSIONS_BASE}/"
            f"CIK{normalized}.json"
        )

    def fetch_company_facts(
        self,
        cik: str | int,
    ) -> dict[str, Any]:

        return self._get_json(
            self.companyfacts_url(cik)
        )

    def fetch_submissions(
        self,
        cik: str | int,
    ) -> dict[str, Any]:

        return self._get_json(
            self.submissions_url(cik)
        )

    # ------------------------------------------------------------------
    # Fact extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _numeric_value(value: Any) -> float | None:

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        try:
            return float(value)

        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:

        try:
            return int(value)

        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_annual_form(form: str | None) -> bool:

        return form == "10-K"

    @staticmethod
    def _is_quarterly_form(form: str | None) -> bool:

        return form in {
            "10-Q",
            "10-K",
        }

    @staticmethod
    def _period_key(
        item: dict[str, Any],
    ) -> tuple[Any, ...]:

        return (
            item.get("fy"),
            item.get("fp"),
            item.get("form"),
            item.get("filed"),
            item.get("start"),
            item.get("end"),
            item.get("accn"),
            item.get("frame"),
        )

    def _make_provenance(
        self,
        *,
        cik: str,
        source_url: str,
        item: dict[str, Any],
    ) -> SECProvenance:

        return SECProvenance(
            source=self.provider_name,
            source_url=source_url,
            retrieved_at=datetime.now(
                timezone.utc
            ).isoformat(),
            form=item.get("form"),
            filed=item.get("filed"),
            accession_number=item.get("accn"),
            cik=cik,
        )

    def extract_concept_records(
        self,
        *,
        companyfacts: dict[str, Any],
        cik: str | int,
        concept: str,
        ticker: str | None = None,
        source_url: str | None = None,
    ) -> list[SECFinancialRecord]:

        normalized_cik = self.normalize_cik(cik)

        facts = companyfacts.get(
            "facts",
            {},
        )

        us_gaap = facts.get(
            "us-gaap",
            {},
        )

        concept_data = us_gaap.get(
            concept
        )

        if not concept_data:
            return []

        units = concept_data.get(
            "units",
            {}
        )

        records: list[SECFinancialRecord] = []

        effective_source_url = (
            source_url
            or self.companyfacts_url(
                normalized_cik
            )
        )

        for unit, values in units.items():

            if not isinstance(values, list):
                continue

            for item in values:

                if not isinstance(item, dict):
                    continue

                value = self._numeric_value(
                    item.get("val")
                )

                if value is None:
                    continue

                form = item.get("form")

                # Only SEC filing-derived financial statements.
                if form not in {
                    "10-K",
                    "10-Q",
                }:
                    continue

                provenance = self._make_provenance(
                    cik=normalized_cik,
                    source_url=effective_source_url,
                    item=item,
                )

                records.append(
                    SECFinancialRecord(
                        ticker=ticker,
                        cik=normalized_cik,
                        concept=concept,
                        label=concept_data.get(
                            "label"
                        ),
                        value=value,
                        unit=unit,
                        fiscal_year=self._safe_int(
                            item.get("fy")
                        ),
                        fiscal_period=item.get(
                            "fp"
                        ),
                        frame=item.get(
                            "frame"
                        ),
                        start_date=item.get(
                            "start"
                        ),
                        end_date=item.get(
                            "end"
                        ),
                        form=form,
                        filed=item.get(
                            "filed"
                        ),
                        accession_number=item.get(
                            "accn"
                        ),
                        provenance=provenance,
                    )
                )

        records.sort(
            key=lambda record: (
                record.end_date or "",
                record.filed or "",
                record.accession_number or "",
            )
        )

        return records

    # ------------------------------------------------------------------
    # Canonical metric extraction
    # ------------------------------------------------------------------

    def extract_normalized_metrics(
        self,
        *,
        companyfacts: dict[str, Any],
        cik: str | int,
        ticker: str | None = None,
    ) -> dict[str, list[SECFinancialRecord]]:

        output: dict[
            str,
            list[SECFinancialRecord],
        ] = {}

        for metric, concepts in CONCEPT_MAP.items():

            metric_records: list[
                SECFinancialRecord
            ] = []

            for concept in concepts:

                records = (
                    self.extract_concept_records(
                        companyfacts=companyfacts,
                        cik=cik,
                        concept=concept,
                        ticker=ticker,
                    )
                )

                if records:
                    metric_records.extend(
                        records
                    )

            # Preserve records but remove
            # exact duplicates.
            unique: dict[
                tuple[Any, ...],
                SECFinancialRecord,
            ] = {}

            for record in metric_records:

                key = (
                    record.concept,
                    record.unit,
                    record.fiscal_year,
                    record.fiscal_period,
                    record.frame,
                    record.start_date,
                    record.end_date,
                    record.filed,
                    record.accession_number,
                    record.value,
                )

                unique[key] = record

            output[metric] = sorted(
                unique.values(),
                key=lambda record: (
                    record.end_date or "",
                    record.filed or "",
                )
            )

        return output

    # ------------------------------------------------------------------
    # Serialization helper
    # ------------------------------------------------------------------

    @staticmethod
    def record_to_dict(
        record: SECFinancialRecord,
    ) -> dict[str, Any]:

        payload = asdict(record)

        return payload


# ----------------------------------------------------------------------
# Offline contract self-test
# ----------------------------------------------------------------------

def self_test() -> None:

    adapter = SECAdapter(
        user_agent="NICK-V3-test test@example.com"
    )

    assert adapter.provider_name == "sec"
    assert adapter.authority == "primary"
    assert adapter.domain == "fundamentals"

    assert (
        adapter.normalize_cik("1045810")
        == "0001045810"
    )

    assert (
        adapter.normalize_cik(1045810)
        == "0001045810"
    )

    assert (
        adapter.companyfacts_url(
            "1045810"
        )
        == (
            "https://data.sec.gov/api/xbrl/"
            "companyfacts/CIK0001045810.json"
        )
    )

    assert (
        adapter.submissions_url(
            "1045810"
        )
        == (
            "https://data.sec.gov/submissions/"
            "CIK0001045810.json"
        )
    )

    fake_companyfacts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenue",
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": 1000000,
                                "accn": "0000000000-25-000001",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-01",
                                "frame": "CY2025",
                            }
                        ]
                    },
                }
            }
        }
    }

    records = adapter.extract_concept_records(
        companyfacts=fake_companyfacts,
        cik="1045810",
        ticker="TEST",
        concept="Revenues",
    )

    assert len(records) == 1
    assert records[0].value == 1000000
    assert records[0].fiscal_year == 2025
    assert records[0].fiscal_period == "FY"
    assert records[0].form == "10-K"
    assert records[0].provenance.source == "sec"
    assert records[0].provenance.cik == "0001045810"

    normalized = adapter.extract_normalized_metrics(
        companyfacts=fake_companyfacts,
        cik="1045810",
        ticker="TEST",
    )

    assert len(
        normalized["revenue"]
    ) == 1

    print(
        "SEC ADAPTER SELF-TEST: PASS"
    )

    print(
        "Network calls executed: 0"
    )


if __name__ == "__main__":
    self_test()

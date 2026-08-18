from __future__ import annotations

import json
import urllib.request

from dataclasses import dataclass, field
from typing import Any

from ai.research.financial.sec_cache import SECCache
from ai.research.governance.api_governor import APIGovernor


@dataclass
class FinancialMetrics:
    ticker: str

    revenue: float = 0
    net_income: float = 0
    assets: float = 0
    liabilities: float = 0
    cashflow: float = 0

    quality_score: float = 0

    currency: str = ""
    source: str = ""
    data_quality: float = 0
    periods_used: int = 0

    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __contains__(self, key):
        return hasattr(self, key)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class FinancialIntelligenceV2:

    SEC_URL = (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    )

    REVENUE_TAGS = (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractsWithCustomers",
        "Revenue",
        "SalesRevenueNet",
        "Revenues",
    )

    NET_INCOME_TAGS = (
        "NetIncomeLoss",
        "ProfitLoss",
        "ProfitLossAttributableToOwnersOfParent",
        "ProfitLossFromContinuingOperations",
    )

    ASSETS_TAGS = (
        "Assets",
    )

    LIABILITIES_TAGS = (
        "Liabilities",
    )

    CURRENT_LIABILITIES_TAGS = (
        "LiabilitiesCurrent",
    )

    NONCURRENT_LIABILITIES_TAGS = (
        "LiabilitiesNoncurrent",
    )

    LIABILITIES_EQUITY_TAGS = (
        "LiabilitiesAndStockholdersEquity",
        "LiabilitiesAndPartnersCapital",
    )

    CASHFLOW_TAGS = (
        "NetCashProvidedByUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivities",
        "CashFlowsFromUsedInOperations",
    )

    PREFERRED_NAMESPACES = (
        "us-gaap",
        "ifrs-full",
    )

    def __init__(self):
        self.cache = SECCache()

        self.governor = APIGovernor(
            daily_limit=1000
        )

        self.headers = {
            "User-Agent": (
                "Trinity-Wealth-Engine "
                "research@example.com"
            )
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, ticker, cik):
        ticker = str(ticker).upper()

        facts = self._load_valid_facts(
            ticker=ticker,
            cik=cik,
        )

        metrics = FinancialMetrics(
            ticker=ticker
        )

        if not facts:
            metrics.source = "unavailable"
            metrics.data_quality = 0
            metrics.quality_score = 0
            return metrics

        extracted = self._extract_metrics(
            facts=facts
        )

        for key, value in extracted.items():
            setattr(metrics, key, value)

        diagnostics = self._validate_semantics(metrics)

        metrics.diagnostics = diagnostics

        metrics.quality_score = self.calculate_quality(
            metrics
        )

        metrics.data_quality = metrics.quality_score

        return metrics

    # ------------------------------------------------------------------
    # Cache / SEC loading
    # ------------------------------------------------------------------

    def _load_valid_facts(self, ticker, cik):
        try:
            if self.cache.exists(ticker):
                cached = self.cache.load(ticker)

                facts = self._extract_facts_from_cache(
                    cached
                )

                if facts:
                    return facts

                print(
                    f"{ticker}: legacy/invalid cache detected; "
                    "refreshing SEC facts"
                )

            if not self.governor.allowed():
                print(
                    f"{ticker}: SEC request blocked by API governor"
                )
                return {}

            self.governor.consume()

            url = self.SEC_URL.format(
                cik=str(cik).zfill(10)
            )

            request = urllib.request.Request(
                url,
                headers=self.headers,
            )

            with urllib.request.urlopen(
                request,
                timeout=10,
            ) as response:
                payload = json.loads(
                    response.read()
                )

            if not isinstance(payload, dict):
                return {}

            facts = payload.get("facts")

            if not isinstance(facts, dict):
                print(
                    f"{ticker}: SEC response has no facts"
                )
                return {}

            self.cache.save(
                ticker,
                cik,
                payload,
            )

            return facts

        except Exception as exc:
            print(
                f"{ticker}: SEC unavailable: {exc}"
            )
            return {}

    @staticmethod
    def _extract_facts_from_cache(cached):
        if not isinstance(cached, dict):
            return {}

        data = cached.get("data")

        if not isinstance(data, dict):
            return {}

        facts = data.get("facts")

        if not isinstance(facts, dict):
            return {}

        if (
            "us-gaap" in facts
            or "ifrs-full" in facts
        ):
            return facts

        return {}

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract_metrics(self, facts):
        namespaces = self._available_namespaces(
            facts
        )

        revenue = self._find_latest_annual_fact(
            facts,
            namespaces,
            self.REVENUE_TAGS,
            flow=True,
        )

        net_income = self._find_latest_annual_fact(
            facts,
            namespaces,
            self.NET_INCOME_TAGS,
            flow=True,
        )

        assets = self._find_latest_annual_fact(
            facts,
            namespaces,
            self.ASSETS_TAGS,
            flow=False,
        )

        liabilities = self._find_liabilities(
            facts,
            namespaces,
        )

        cashflow = self._find_latest_annual_fact(
            facts,
            namespaces,
            self.CASHFLOW_TAGS,
            flow=True,
        )

        values = {
            "revenue": revenue["value"],
            "net_income": net_income["value"],
            "assets": assets["value"],
            "liabilities": liabilities["value"],
            "cashflow": cashflow["value"],
            "currency": (
                revenue["currency"]
                or net_income["currency"]
                or assets["currency"]
                or liabilities["currency"]
                or cashflow["currency"]
            ),
            "source": "SEC Company Facts",
            "periods_used": sum(
                1
                for item in (
                    revenue,
                    net_income,
                    assets,
                    liabilities,
                    cashflow,
                )
                if item["value"] != 0
            ),
            "diagnostics": {
                "revenue": revenue,
                "net_income": net_income,
                "assets": assets,
                "liabilities": liabilities,
                "cashflow": cashflow,
            },
        }

        return values

    @staticmethod
    def _available_namespaces(facts):
        result = []

        for namespace in (
            "us-gaap",
            "ifrs-full",
        ):
            if isinstance(
                facts.get(namespace),
                dict,
            ):
                result.append(namespace)

        return result

    # ------------------------------------------------------------------
    # Liabilities
    # ------------------------------------------------------------------

    def _find_liabilities(
        self,
        facts,
        namespaces,
    ):
        direct = self._find_latest_annual_fact(
            facts,
            namespaces,
            self.LIABILITIES_TAGS,
            flow=False,
        )

        if direct["value"] != 0:
            direct["method"] = "direct"
            return direct

        current = self._find_latest_annual_fact(
            facts,
            namespaces,
            self.CURRENT_LIABILITIES_TAGS,
            flow=False,
        )

        noncurrent = self._find_latest_annual_fact(
            facts,
            namespaces,
            self.NONCURRENT_LIABILITIES_TAGS,
            flow=False,
        )

        if (
            current["value"] != 0
            and noncurrent["value"] != 0
        ):
            same_currency = (
                current["currency"]
                == noncurrent["currency"]
            )

            if same_currency:
                combined = (
                    current["value"]
                    + noncurrent["value"]
                )

                return {
                    "value": combined,
                    "currency": current["currency"],
                    "method": (
                        "current_plus_noncurrent"
                    ),
                    "tag": (
                        "LiabilitiesCurrent"
                        "+"
                        "LiabilitiesNoncurrent"
                    ),
                    "annual": min(
                        current.get("annual", 0),
                        noncurrent.get("annual", 0),
                    ),
                    "end": min(
                        current.get("end", ""),
                        noncurrent.get("end", ""),
                    ),
                    "filed": max(
                        current.get("filed", ""),
                        noncurrent.get("filed", ""),
                    ),
                }

        fallback = self._find_latest_annual_fact(
            facts,
            namespaces,
            self.LIABILITIES_EQUITY_TAGS,
            flow=False,
        )

        if fallback["value"] != 0:
            fallback["method"] = (
                "liabilities_and_equity_fallback"
            )
            return fallback

        return {
            "value": 0,
            "currency": "",
            "method": "unavailable",
        }

    # ------------------------------------------------------------------
    # Annual fact selection
    # ------------------------------------------------------------------

    def _find_latest_annual_fact(
        self,
        facts,
        namespaces,
        tags,
        flow,
    ):
        candidates = []

        for namespace in namespaces:
            namespace_data = facts.get(
                namespace,
                {}
            )

            if not isinstance(namespace_data, dict):
                continue

            for tag_priority, tag in enumerate(tags):
                tag_data = namespace_data.get(tag)

                if not isinstance(tag_data, dict):
                    continue

                units = tag_data.get(
                    "units",
                    {}
                )

                if not isinstance(units, dict):
                    continue

                for unit_name, records in units.items():
                    if not isinstance(records, list):
                        continue

                    for record in records:
                        candidate = self._normalize_record(
                            record=record,
                            unit_name=unit_name,
                            flow=flow,
                        )

                        if candidate is None:
                            continue

                        candidate["namespace"] = namespace
                        candidate["tag"] = tag
                        candidate["tag_priority"] = (
                            tag_priority
                        )

                        candidates.append(candidate)

                # Do not stop simply because a tag exists.
                # Higher-quality annual candidates still need
                # to be compared.

        if not candidates:
            return {
                "value": 0,
                "currency": "",
                "annual": 0,
                "end": "",
                "filed": "",
                "tag": "",
            }

        candidates.sort(
            key=lambda item: (
                item["annual"],
                item["duration_quality"],
                item["end"],
                item["filed"],
                -item["tag_priority"],
            ),
            reverse=True,
        )

        best = candidates[0]

        return {
            "value": best["value"],
            "currency": best["currency"],
            "annual": best["annual"],
            "end": best["end"],
            "filed": best["filed"],
            "tag": best["tag"],
            "namespace": best["namespace"],
        }

    @staticmethod
    def _normalize_record(
        record,
        unit_name,
        flow,
    ):
        if not isinstance(record, dict):
            return None

        if "val" not in record:
            return None

        try:
            value = float(record["val"])
        except (
            TypeError,
            ValueError,
        ):
            return None

        end = str(
            record.get("end", "")
        )

        if not end:
            return None

        start = str(
            record.get("start", "")
        )

        form = str(
            record.get("form", "")
        ).upper()

        fp = str(
            record.get("fp", "")
        ).upper()

        frame = str(
            record.get("frame", "")
        ).upper()

        annual = False

        if fp == "FY":
            annual = True

        if (
            frame.startswith("CY")
            and (
                len(frame) == 6
                or "FY" in frame
            )
        ):
            annual = True

        if form in {
            "10-K",
            "10-K/A",
            "20-F",
            "20-F/A",
            "40-F",
            "40-F/A",
        }:
            if flow:
                if start:
                    annual = True
            else:
                annual = True

        duration_quality = 0

        if flow:
            if not start:
                return None

            try:
                start_year = int(start[:4])
                end_year = int(end[:4])
            except ValueError:
                return None

            duration_years = (
                end_year - start_year
            )

            if duration_years < 0:
                return None

            if duration_years > 1:
                return None

            if (
                duration_years == 0
                and not annual
            ):
                return None

            if annual:
                duration_quality = 2
            else:
                duration_quality = 1

        else:
            if annual:
                duration_quality = 2
            else:
                duration_quality = 1

        currency = unit_name

        return {
            "value": value,
            "currency": currency,
            "annual": int(annual),
            "duration_quality": duration_quality,
            "end": end,
            "filed": str(
                record.get("filed", "")
            ),
        }

    # ------------------------------------------------------------------
    # Semantic validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_semantics(financial):
        warnings = []
        errors = []

        revenue = financial.revenue
        net_income = financial.net_income
        assets = financial.assets
        liabilities = financial.liabilities
        cashflow = financial.cashflow

        if revenue <= 0:
            errors.append(
                "Revenue is missing or non-positive."
            )

        if net_income == 0:
            warnings.append(
                "Net income is zero or unavailable."
            )

        if assets <= 0:
            errors.append(
                "Assets are missing or non-positive."
            )

        if liabilities < 0:
            errors.append(
                "Liabilities are negative."
            )

        if assets > 0 and liabilities > assets:
            warnings.append(
                "Liabilities exceed total assets."
            )

        if (
            revenue > 0
            and abs(net_income) > revenue * 2
        ):
            errors.append(
                "Net income is implausibly large "
                "relative to revenue."
            )

        if (
            revenue > 0
            and abs(cashflow) > revenue * 2
        ):
            warnings.append(
                "Operating cash flow is unusually "
                "large relative to revenue."
            )

        if (
            revenue > 0
            and assets > revenue * 20
        ):
            warnings.append(
                "Assets are unusually large "
                "relative to revenue."
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "metrics": {
                "revenue": revenue,
                "net_income": net_income,
                "assets": assets,
                "liabilities": liabilities,
                "cashflow": cashflow,
            },
        }

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------

    def calculate_quality(
        self,
        financial,
    ):
        score = 0

        diagnostics = getattr(
            financial,
            "diagnostics",
            {},
        )

        if financial.revenue > 0:
            score += 20

        if financial.net_income != 0:
            score += 20

        if financial.cashflow != 0:
            score += 20

        if (
            financial.assets > 0
            and financial.assets >= financial.liabilities
        ):
            score += 20

        if diagnostics.get("valid", False):
            score += 20

        return min(
            score,
            100,
        )

    def quality_score(
        self,
        financial,
    ):
        return self.calculate_quality(
            financial
        )

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


@dataclass(frozen=True)
class SecurityMasterRecord:
    """
    Canonical identity and classification contract.

    Security Master deliberately does NOT contain:
        - price
        - market capitalization
        - valuation
        - financial quality
        - ranking
        - investment recommendation
    """

    security_id: str
    ticker: str
    company_name: str
    exchange: str
    cik: int | None
    country: str

    instrument_type: str
    classification_confidence: str
    investable_equity: bool
    classification_reason: str

    source: str = "SEC"
    source_url: str = (
        "https://www.sec.gov/files/"
        "company_tickers_exchange.json"
    )

    identity_confidence: str = "high"

    identifiers: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] | None = None

    data_quality: str = "good"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SecurityMaster:
    """
    ATLAS canonical security classification layer V3.

    Important design rule:

        SEC universe discovery
                |
                v
        Security Master
                |
                +--> identity
                +--> instrument classification
                +--> investability
                |
                v
        downstream research

    Classification is deliberately conservative.

    Ticker suffixes such as W/R/U are NOT sufficient by themselves
    because legitimate common-equity tickers may also end in those
    characters.

    Suffix-based classification is only activated when supported by
    issuer/name context.
    """

    SOURCE = "SEC"

    SOURCE_URL = (
        "https://www.sec.gov/files/"
        "company_tickers_exchange.json"
    )

    EXCLUDED_PATTERNS = (
        "WARRANT",
        "WARRANTS",
        "RIGHT",
        "RIGHTS",
        "UNIT",
        "UNITS",
    )

    PREFERRED_PATTERNS = (
        "PREFERRED",
        "PREFERENCE SHARES",
        "PREFERENCE SHARE",
        "PREF ",
        "PREF/",
    )

    DEBT_PATTERNS = (
        "NOTE",
        "NOTES",
        "DEBENTURE",
        "BOND",
        "BONDS",
        "SENIOR NOTE",
        "SENIOR NOTES",
        "SENIOR DEBT",
        "CONVERTIBLE NOTE",
        "CONVERTIBLE NOTES",
    )

    FUND_PATTERNS = (
        "ETF",
        "ETN",
        "FUND",
        "MUTUAL FUND",
        "INDEX FUND",
        "EXCHANGE TRADED FUND",
        "EXCHANGE-TRADED FUND",
    )

    REIT_PATTERNS = (
        "REIT",
        "REAL ESTATE INVESTMENT TRUST",
    )

    ACQUISITION_PATTERNS = (
        "ACQUISITION",
        "ACQUISITION CORP",
        "ACQUISITION COMPANY",
        "SPECIAL PURPOSE ACQUISITION",
        "SPAC",
    )

    UNIT_SUFFIXES = (
        "U",
    )

    WARRANT_SUFFIXES = (
        "W",
        "WS",
        "WT",
        "WW",
    )

    RIGHT_SUFFIXES = (
        "R",
        "RT",
    )

    def build(
        self,
        universe: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        for item in universe:
            normalized = self._normalize_input(item)

            if normalized is None:
                continue

            record = self._classify(normalized)
            result.append(record.to_dict())

        return result

    def investable_only(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            record
            for record in records
            if record.get("investable_equity") is True
        ]

    def summarize(
        self,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:

        counts: dict[str, int] = {}
        confidence_counts: dict[str, int] = {}
        quality_counts: dict[str, int] = {}

        investable = 0

        for record in records:
            instrument_type = str(
                record.get(
                    "instrument_type",
                    "UNKNOWN",
                )
            )

            counts[instrument_type] = (
                counts.get(instrument_type, 0) + 1
            )

            if record.get("investable_equity") is True:
                investable += 1

            classification_confidence = str(
                record.get(
                    "classification_confidence",
                    "unknown",
                )
            )

            confidence_counts[classification_confidence] = (
                confidence_counts.get(
                    classification_confidence,
                    0,
                )
                + 1
            )

            quality = str(
                record.get(
                    "data_quality",
                    "unknown",
                )
            )

            quality_counts[quality] = (
                quality_counts.get(quality, 0) + 1
            )

        total = len(records)

        return {
            "total": total,
            "investable_equity": investable,
            "non_investable": total - investable,
            "instrument_counts": counts,
            "classification_confidence_counts": confidence_counts,
            "data_quality_counts": quality_counts,
        }

    # ============================================================
    # NORMALIZATION
    # ============================================================

    def _normalize_input(
        self,
        item: dict[str, Any],
    ) -> dict[str, Any] | None:

        ticker = str(
            item.get("ticker", "")
        ).strip().upper()

        company_name = str(
            item.get(
                "company_name",
                item.get("name", ""),
            )
        ).strip()

        exchange = str(
            item.get("exchange", "")
        ).strip().upper()

        if not ticker:
            return None

        if not company_name:
            return None

        if not exchange:
            return None

        cik = self._normalize_cik(
            item.get("cik")
        )

        country = str(
            item.get(
                "country",
                "US",
            )
        ).strip().upper()

        if not country:
            country = "US"

        return {
            "ticker": ticker,
            "company_name": company_name,
            "exchange": exchange,
            "cik": cik,
            "country": country,
        }

    @staticmethod
    def _normalize_cik(
        value: Any,
    ) -> int | None:

        if value is None:
            return None

        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None

        if parsed <= 0:
            return None

        return parsed

    # ============================================================
    # CLASSIFICATION
    # ============================================================

    def _classify(
        self,
        item: dict[str, Any],
    ) -> SecurityMasterRecord:

        ticker = item["ticker"]
        company_name = item["company_name"]
        exchange = item["exchange"]
        cik = item["cik"]
        country = item["country"]

        text = self._classification_text(
            ticker,
            company_name,
        )

        instrument_type = "COMMON_EQUITY"
        confidence = "medium"
        investable = True

        reason = (
            "SEC universe record classified as "
            "common-equity candidate."
        )

        # --------------------------------------------------------
        # 1. Explicit instrument wording has highest priority.
        # --------------------------------------------------------

        if self._matches(
            text,
            self.EXCLUDED_PATTERNS,
        ):
            instrument_type = self._explicit_special_type(text)
            confidence = "high"
            investable = False

            reason = (
                "Security name explicitly indicates "
                f"{instrument_type.lower()}."
            )

        elif self._matches(
            text,
            self.PREFERRED_PATTERNS,
        ):
            instrument_type = "PREFERRED_EQUITY"
            confidence = "high"
            investable = False

            reason = (
                "Security name explicitly indicates "
                "preferred equity."
            )

        elif self._matches(
            text,
            self.DEBT_PATTERNS,
        ):
            instrument_type = "DEBT"
            confidence = "high"
            investable = False

            reason = (
                "Security name explicitly indicates "
                "debt instrument."
            )

        elif self._matches(
            text,
            self.FUND_PATTERNS,
        ):
            instrument_type = "FUND_OR_ETF"
            confidence = "high"
            investable = False

            reason = (
                "Security name explicitly indicates "
                "fund or exchange-traded instrument."
            )

        elif self._matches(
            text,
            self.REIT_PATTERNS,
        ):
            instrument_type = "REIT"
            confidence = "medium"
            investable = True

            reason = (
                "Security name indicates a REIT. "
                "Retained as investable equity."
            )

        # --------------------------------------------------------
        # 2. Context-aware suffix classification.
        #
        # NEVER classify W/R/U merely because the ticker ends
        # with that character.
        #
        # We require acquisition/SPAC-like issuer context.
        # --------------------------------------------------------

        elif self._is_acquisition_issuer(company_name):

            suffix_type = self._classify_acquisition_suffix(
                ticker
            )

            if suffix_type is not None:
                instrument_type = suffix_type
                confidence = "high"
                investable = False

                reason = (
                    "Ticker suffix is consistent with a "
                    "non-common instrument issued by an "
                    "acquisition/SPAC entity."
                )

        security_id = self._build_security_id(
            exchange=exchange,
            ticker=ticker,
            cik=cik,
        )

        identity_confidence = (
            "high"
            if cik is not None
            else "medium"
        )

        data_quality = self._data_quality(
            ticker=ticker,
            company_name=company_name,
            exchange=exchange,
            cik=cik,
            country=country,
        )

        identifiers = {
            "ticker": ticker,
            "cik": cik,
            "exchange": exchange,
        }

        evidence = [
            {
                "type": "primary_source",
                "source": self.SOURCE,
                "url": self.SOURCE_URL,
                "description": (
                    "SEC company ticker, CIK, and "
                    "exchange association."
                ),
            },
            {
                "type": "classification",
                "source": "ATLAS_SECURITY_MASTER_V3",
                "description": reason,
            },
        ]

        return SecurityMasterRecord(
            security_id=security_id,
            ticker=ticker,
            company_name=company_name,
            exchange=exchange,
            cik=cik,
            country=country,
            instrument_type=instrument_type,
            classification_confidence=confidence,
            investable_equity=investable,
            classification_reason=reason,
            source=self.SOURCE,
            source_url=self.SOURCE_URL,
            identity_confidence=identity_confidence,
            identifiers=identifiers,
            evidence=evidence,
            data_quality=data_quality,
        )

    # ============================================================
    # CLASSIFICATION HELPERS
    # ============================================================

    @staticmethod
    def _explicit_special_type(
        text: str,
    ) -> str:

        if re.search(r"\bWARRANTS?\b", text):
            return "WARRANT"

        if re.search(r"\bRIGHTS?\b", text):
            return "RIGHT"

        if re.search(r"\bUNITS?\b", text):
            return "UNIT"

        return "DERIVATIVE_OR_SPECIAL"

    def _classify_acquisition_suffix(
        self,
        ticker: str,
    ) -> str | None:

        if ticker.endswith(self.WARRANT_SUFFIXES):
            return "WARRANT"

        if ticker.endswith(self.RIGHT_SUFFIXES):
            return "RIGHT"

        if ticker.endswith(self.UNIT_SUFFIXES):
            return "UNIT"

        return None

    def _is_acquisition_issuer(
        self,
        company_name: str,
    ) -> bool:

        text = str(company_name).upper()

        return self._matches(
            text,
            self.ACQUISITION_PATTERNS,
        )

    @staticmethod
    def _classification_text(
        ticker: str,
        company_name: str,
    ) -> str:

        return re.sub(
            r"\s+",
            " ",
            f"{ticker} {company_name}".upper(),
        ).strip()

    @staticmethod
    def _matches(
        text: str,
        patterns: tuple[str, ...],
    ) -> bool:

        for pattern in patterns:
            escaped = re.escape(pattern)

            if re.search(
                rf"(?<![A-Z0-9]){escaped}(?![A-Z0-9])",
                text,
            ):
                return True

        return False

    # ============================================================
    # IDENTITY
    # ============================================================

    @staticmethod
    def _build_security_id(
        *,
        exchange: str,
        ticker: str,
        cik: int | None,
    ) -> str:

        if cik is not None:
            return (
                f"US:{exchange}:"
                f"CIK{cik:010d}:"
                f"{ticker}"
            )

        return (
            f"US:{exchange}:"
            f"{ticker}"
        )

    # ============================================================
    # DATA QUALITY
    # ============================================================

    @staticmethod
    def _data_quality(
        *,
        ticker: str,
        company_name: str,
        exchange: str,
        cik: int | None,
        country: str,
    ) -> str:

        if not ticker:
            return "invalid"

        if not company_name:
            return "invalid"

        if not exchange:
            return "invalid"

        if not country:
            return "degraded"

        if cik is None:
            return "degraded"

        return "good"

"""
ATLAS US Stock Scout.

Real universe discovery source:
    SEC company_tickers_exchange.json

Responsibilities:
    - Discover US-listed equity candidates.
    - Normalize ticker / CIK / company / exchange.
    - Restrict the universe to configured US exchanges.
    - Deduplicate securities.
    - Return AgentResult evidence.

Non-responsibilities:
    - No valuation.
    - No ranking.
    - No investment decision.
    - No financial recommendation.

This is the universe-discovery layer only.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ai.agent_result import AgentResult


class USStockScout:

    name = "US Stock Scout"

    SEC_URL = (
        "https://www.sec.gov/files/"
        "company_tickers_exchange.json"
    )

    DEFAULT_EXCHANGES = {
        "NYSE",
        "NASDAQ",
        "AMEX",
    }

    CACHE_DIR = Path(".atlas_cache")
    CACHE_FILE = CACHE_DIR / "sec_company_tickers_exchange.json"

    CACHE_MAX_AGE_SECONDS = 24 * 60 * 60

    def __init__(
        self,
        *,
        exchanges: set[str] | None = None,
        cache_file: str | Path | None = None,
        user_agent: str | None = None,
        timeout: int = 30,
    ) -> None:

        self.exchanges = {
            str(value).strip().upper()
            for value in (
                exchanges
                or self.DEFAULT_EXCHANGES
            )
        }

        self.cache_file = Path(
            cache_file
            or self.CACHE_FILE
        )

        self.user_agent = (
            user_agent
            or os.getenv(
                "SEC_USER_AGENT",
                "ATLAS Investment Research "
                "(research@example.com)",
            )
        )

        self.timeout = timeout

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------

    def resolve_ticker(
        self,
        ticker: str,
    ) -> dict[str, Any] | None:
        """
        Resolve one explicit US ticker directly from SEC.

        This method intentionally does NOT perform a full-market scan.
        It reuses the existing SEC source/cache infrastructure.
        """

        if not isinstance(ticker, str):
            return None

        normalized = ticker.strip().upper()

        if not normalized:
            return None

        payload, source = self._load_source()
        records = self._extract_records(payload)

        for record in records:
            candidate = str(
                record.get("ticker", "")
            ).strip().upper()

            if candidate != normalized:
                continue

            exchange = str(
                record.get("exchange", "")
            ).strip().upper()

            if exchange not in self.exchanges:
                return None

            cik_raw = record.get("cik")

            try:
                cik = int(cik_raw)
            except (TypeError, ValueError):
                cik = None

            company_name = str(
                record.get("name", "")
            ).strip()

            if not company_name:
                return None

            return {
                "ticker": normalized,
                "company_name": company_name,
                "exchange": exchange,
                "cik": cik,
                "security_type": "equity",
                "country": "US",
                "resolution_mode": "direct_sec_lookup",
                "identity_status": (
                    "resolved"
                    if cik is not None
                    else "degraded"
                ),
                "identity_source": source,
                "source": "SEC",
                "source_url": self.SEC_URL,
            }

        return None

    def scan(self) -> AgentResult:

        started = time.time()

        try:

            payload, source = self._load_source()

            records = self._extract_records(payload)

            universe = self._normalize_records(records)

            universe = [
                item
                for item in universe
                if item["exchange"] in self.exchanges
            ]

            universe = self._deduplicate(universe)

            elapsed = round(
                time.time() - started,
                3,
            )

            if not universe:
                return AgentResult(
                    agent=self.name,
                    status="failure",
                    summary=(
                        "SEC universe discovery returned "
                        "zero configured US equities."
                    ),
                    data={
                        "market": "US",
                        "universe": [],
                        "stage": "universe_discovery",
                        "source": source,
                    },
                    warnings=[
                        "No securities matched configured exchanges."
                    ],
                )

            exchange_counts: dict[str, int] = {}

            for item in universe:

                exchange = item["exchange"]

                exchange_counts[exchange] = (
                    exchange_counts.get(exchange, 0) + 1
                )

            return AgentResult(
                agent=self.name,
                status="success",
                summary=(
                    f"Discovered {len(universe)} US-listed "
                    f"equity candidates from SEC."
                ),
                data={
                    "market": "US",
                    "stage": "universe_discovery",
                    "source": source,
                    "source_url": self.SEC_URL,
                    "exchange_filter": sorted(
                        self.exchanges
                    ),
                    "count": len(universe),
                    "exchange_counts": exchange_counts,
                    "elapsed_seconds": elapsed,
                    "universe": universe,
                },
                evidence=[
                    {
                        "type": "primary_source",
                        "source": "SEC",
                        "url": self.SEC_URL,
                        "description": (
                            "SEC company ticker and "
                            "exchange associations."
                        ),
                    }
                ],
            )

        except Exception as exc:

            return AgentResult(
                agent=self.name,
                status="failure",
                summary=(
                    "US equity universe discovery failed."
                ),
                data={
                    "market": "US",
                    "stage": "universe_discovery",
                },
                warnings=[
                    repr(exc),
                ],
            )

    # ------------------------------------------------------------
    # SOURCE LOADING
    # ------------------------------------------------------------

    def _load_source(
        self,
    ) -> tuple[dict[str, Any], str]:

        if self._cache_is_fresh():

            return (
                self._read_json(self.cache_file),
                "SEC_CACHE",
            )

        try:

            payload = self._download_sec()

            self._write_cache(payload)

            return (
                payload,
                "SEC_LIVE",
            )

        except Exception:

            if self.cache_file.exists():

                return (
                    self._read_json(
                        self.cache_file
                    ),
                    "SEC_CACHE_FALLBACK",
                )

            raise

    def _download_sec(
        self,
    ) -> dict[str, Any]:

        request = Request(
            self.SEC_URL,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
            method="GET",
        )

        try:

            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:

                raw = response.read()

        except HTTPError as exc:

            raise RuntimeError(
                f"SEC HTTP error: {exc.code}"
            ) from exc

        except URLError as exc:

            raise RuntimeError(
                f"SEC network error: {exc.reason}"
            ) from exc

        except TimeoutError as exc:

            raise RuntimeError(
                "SEC request timed out."
            ) from exc

        try:

            return json.loads(
                raw.decode(
                    "utf-8",
                    errors="replace",
                )
            )

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "SEC returned invalid JSON."
            ) from exc

    # ------------------------------------------------------------
    # CACHE
    # ------------------------------------------------------------

    def _cache_is_fresh(self) -> bool:

        if not self.cache_file.exists():
            return False

        try:

            age = (
                time.time()
                - self.cache_file.stat().st_mtime
            )

            return age <= self.CACHE_MAX_AGE_SECONDS

        except OSError:

            return False

    def _read_json(
        self,
        path: Path,
    ) -> dict[str, Any]:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    def _write_cache(
        self,
        payload: dict[str, Any],
    ) -> None:

        self.cache_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.cache_file.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # ------------------------------------------------------------
    # NORMALIZATION
    # ------------------------------------------------------------

    def _extract_records(
        self,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:

        fields = payload.get("fields")

        data = payload.get("data")

        if not isinstance(fields, list):
            raise ValueError(
                "SEC payload missing fields."
            )

        if not isinstance(data, list):
            raise ValueError(
                "SEC payload missing data."
            )

        field_index = {
            str(name): index
            for index, name in enumerate(fields)
        }

        required = [
            "cik",
            "name",
            "ticker",
            "exchange",
        ]

        missing = [
            name
            for name in required
            if name not in field_index
        ]

        if missing:
            raise ValueError(
                "SEC payload missing fields: "
                + ", ".join(missing)
            )

        result = []

        for row in data:

            if not isinstance(row, list):
                continue

            item = {}

            for name, index in field_index.items():

                if index < len(row):

                    item[name] = row[index]

            result.append(item)

        return result

    def _normalize_records(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        normalized = []

        for record in records:

            ticker = str(
                record.get("ticker", "")
            ).strip().upper()

            name = str(
                record.get("name", "")
            ).strip()

            exchange = str(
                record.get("exchange", "")
            ).strip().upper()

            cik_raw = record.get("cik")

            if not ticker:
                continue

            if not name:
                continue

            if not exchange:
                continue

            try:

                cik = int(cik_raw)

            except (
                TypeError,
                ValueError,
            ):

                cik = None

            normalized.append(
                {
                    "ticker": ticker,
                    "company_name": name,
                    "exchange": exchange,
                    "cik": cik,
                    "security_type": "equity",
                    "country": "US",
                }
            )

        return normalized

    def _deduplicate(
        self,
        universe: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        seen: set[tuple[str, str]] = set()

        result = []

        for item in universe:

            key = (
                item["ticker"],
                item["exchange"],
            )

            if key in seen:
                continue

            seen.add(key)

            result.append(item)

        result.sort(
            key=lambda item: (
                item["exchange"],
                item["ticker"],
            )
        )

        return result

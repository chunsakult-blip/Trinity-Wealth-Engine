from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

from .sec_request_policy import (
    SECRequestPolicy,
    SECRequestRateGuard,
)

from .sec_response_validator import (
    validate_company_facts_response,
    validate_submissions_response,
)


SEC_DATA_BASE_URL = "https://data.sec.gov"


class SECFetchError(RuntimeError):
    """Raised when a SEC live request fails."""


@dataclass(frozen=True)
class SECFetchResult:
    endpoint: str
    url: str
    payload: Mapping[str, Any]
    status_code: int


class SECLiveFetcher:
    """
    Thin live transport layer for SEC public APIs.

    Responsibilities:
      - construct SEC URLs
      - validate local request policy
      - identify client with User-Agent
      - enforce local pacing
      - perform HTTP GET
      - decode JSON
      - validate endpoint-specific structure

    Non-responsibilities:
      - financial calculations
      - concept mapping
      - period normalization
      - valuation
      - ingestion orchestration
    """

    def __init__(
        self,
        *,
        user_agent: str,
        base_url: str = SEC_DATA_BASE_URL,
        policy: Optional[SECRequestPolicy] = None,
    ) -> None:

        self.policy = (
            policy
            if policy is not None
            else SECRequestPolicy()
        )

        self.user_agent = (
            self.policy.validate_user_agent(
                user_agent
            )
        )

        self.base_url = base_url.rstrip("/")

        self.policy.validate_timeout()
        self.policy.validate_retries()
        self.policy.validate_interval()

        self.rate_guard = SECRequestRateGuard(
            self.policy.min_interval_seconds
        )

    # ------------------------------------------------------------------
    # URL builders
    # ------------------------------------------------------------------

    def companyfacts_url(
        self,
        cik: str,
    ) -> str:

        normalized_cik = self._normalize_cik(cik)

        return (
            f"{self.base_url}/api/xbrl/companyfacts/"
            f"CIK{normalized_cik}.json"
        )

    def submissions_url(
        self,
        cik: str,
    ) -> str:

        normalized_cik = self._normalize_cik(cik)

        return (
            f"{self.base_url}/submissions/"
            f"CIK{normalized_cik}.json"
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def fetch_company_facts(
        self,
        cik: str,
    ) -> SECFetchResult:

        url = self.companyfacts_url(cik)

        result = self._get_json(
            url=url,
            endpoint="companyfacts",
        )

        payload = validate_company_facts_response(
            result.payload
        )

        return SECFetchResult(
            endpoint=result.endpoint,
            url=result.url,
            payload=payload,
            status_code=result.status_code,
        )

    def fetch_submissions(
        self,
        cik: str,
    ) -> SECFetchResult:

        url = self.submissions_url(cik)

        result = self._get_json(
            url=url,
            endpoint="submissions",
        )

        payload = validate_submissions_response(
            result.payload
        )

        return SECFetchResult(
            endpoint=result.endpoint,
            url=result.url,
            payload=payload,
            status_code=result.status_code,
        )

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _get_json(
        self,
        *,
        url: str,
        endpoint: str,
    ) -> SECFetchResult:

        retries = self.policy.max_retries

        last_error: Optional[Exception] = None

        for attempt in range(
            retries + 1
        ):

            self.rate_guard.wait_if_required()

            request = Request(
                url=url,
                method="GET",
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                },
            )

            self.rate_guard.mark_request()

            try:

                with urlopen(
                    request,
                    timeout=self.policy.timeout_seconds,
                ) as response:

                    status_code = int(
                        response.status
                    )

                    raw = response.read()

                payload = json.loads(
                    raw.decode("utf-8")
                )

                if not isinstance(
                    payload,
                    Mapping,
                ):
                    raise SECFetchError(
                        "SEC returned non-object JSON"
                    )

                return SECFetchResult(
                    endpoint=endpoint,
                    url=url,
                    payload=payload,
                    status_code=status_code,
                )

            except HTTPError as exc:

                last_error = exc

                if attempt >= retries:
                    raise SECFetchError(
                        f"SEC HTTP error "
                        f"{exc.code} "
                        f"for {endpoint}"
                    ) from exc

            except (
                URLError,
                TimeoutError,
                json.JSONDecodeError,
                OSError,
            ) as exc:

                last_error = exc

                if attempt >= retries:
                    raise SECFetchError(
                        f"SEC request failed "
                        f"for {endpoint}: {exc}"
                    ) from exc

        raise SECFetchError(
            f"SEC request failed for {endpoint}"
        ) from last_error

    # ------------------------------------------------------------------
    # CIK normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_cik(
        cik: str,
    ) -> str:

        if cik is None:
            raise ValueError(
                "CIK is required"
            )

        value = str(cik).strip()

        if value.upper().startswith("CIK"):
            value = value[3:]

        value = value.strip()

        if not value.isdigit():
            raise ValueError(
                f"Invalid SEC CIK: {cik}"
            )

        return value.zfill(10)

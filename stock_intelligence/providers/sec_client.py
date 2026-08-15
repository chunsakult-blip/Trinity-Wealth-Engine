from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SEC_COMPANY_FACTS_URL = (
    "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
)


@dataclass
class SECClientConfig:
    user_agent: str
    timeout_seconds: float = 20.0
    min_interval_seconds: float = 0.20
    max_retries: int = 3
    backoff_seconds: float = 1.0


class SECClientError(RuntimeError):
    pass


class SECClient:
    """
    Canonical SEC Company Facts client.

    Production responsibilities:
      - SEC User-Agent declaration
      - request timeout
      - retry handling
      - basic rate limiting
      - JSON validation
      - optional local cache
    """

    def __init__(
        self,
        config: SECClientConfig,
        *,
        opener=urlopen,
        sleep=time.sleep,
        clock=time.monotonic,
    ) -> None:

        if not config.user_agent.strip():
            raise ValueError(
                "SEC user_agent must be non-empty"
            )

        self.config = config
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: Optional[float] = None

    def _respect_rate_limit(self) -> None:

        if self._last_request_at is None:
            return

        elapsed = (
            self._clock()
            - self._last_request_at
        )

        remaining = (
            self.config.min_interval_seconds
            - elapsed
        )

        if remaining > 0:
            self._sleep(remaining)

    @staticmethod
    def normalize_cik(cik: str | int) -> str:

        digits = "".join(
            character
            for character in str(cik)
            if character.isdigit()
        )

        if not digits:
            raise ValueError(
                "CIK must contain digits"
            )

        return digits.zfill(10)

    def build_company_facts_url(
        self,
        cik: str | int,
    ) -> str:

        normalized = self.normalize_cik(cik)

        return SEC_COMPANY_FACTS_URL.format(
            cik=normalized
        )

    def fetch_json(
        self,
        url: str,
    ) -> Mapping[str, Any]:

        if not url.startswith(
            "https://data.sec.gov/"
        ):
            raise ValueError(
                "SEC client only permits data.sec.gov URLs"
            )

        last_error: Optional[Exception] = None

        for attempt in range(
            self.config.max_retries + 1
        ):

            self._respect_rate_limit()

            request = Request(
                url,
                headers={
                    "User-Agent":
                        self.config.user_agent,
                    "Accept":
                        "application/json",
                    "Accept-Encoding":
                        "gzip, deflate",
                },
                method="GET",
            )

            try:

                self._last_request_at = self._clock()

                with self._opener(
                    request,
                    timeout=self.config.timeout_seconds,
                ) as response:

                    payload = response.read()

                decoded = payload.decode(
                    "utf-8"
                )

                data = json.loads(decoded)

                if not isinstance(data, Mapping):
                    raise SECClientError(
                        "SEC response is not a JSON object"
                    )

                return data

            except HTTPError as exc:

                last_error = exc

                if exc.code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                } and attempt < self.config.max_retries:

                    delay = (
                        self.config.backoff_seconds
                        * (2 ** attempt)
                    )

                    self._sleep(delay)
                    continue

                raise SECClientError(
                    f"SEC HTTP error: {exc.code}"
                ) from exc

            except (
                URLError,
                TimeoutError,
                json.JSONDecodeError,
            ) as exc:

                last_error = exc

                if attempt < self.config.max_retries:

                    delay = (
                        self.config.backoff_seconds
                        * (2 ** attempt)
                    )

                    self._sleep(delay)
                    continue

                raise SECClientError(
                    "SEC request failed"
                ) from exc

            except SECClientError:
                raise

        raise SECClientError(
            "SEC request failed"
        ) from last_error

    def fetch_company_facts(
        self,
        cik: str | int,
    ) -> Mapping[str, Any]:

        url = self.build_company_facts_url(
            cik
        )

        return self.fetch_json(url)

    @staticmethod
    def validate_company_facts(
        payload: Mapping[str, Any],
    ) -> None:

        required_keys = {
            "cik",
            "entityName",
            "facts",
        }

        missing = (
            required_keys
            - set(payload.keys())
        )

        if missing:
            raise SECClientError(
                "SEC Company Facts payload "
                f"missing keys: {sorted(missing)}"
            )

        if not isinstance(
            payload["facts"],
            Mapping,
        ):
            raise SECClientError(
                "SEC Company Facts 'facts' "
                "must be an object"
            )


def create_default_sec_client(
    user_agent: str,
) -> SECClient:

    return SECClient(
        SECClientConfig(
            user_agent=user_agent,
        )
    )

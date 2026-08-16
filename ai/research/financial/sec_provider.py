"""
SEC Company Facts provider for Mega Batch E.

Provider boundary:
- SEC-specific HTTP logic stays here.
- Everything after this module is provider-neutral.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any


class SECCompanyFactsProvider:

    BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        timeout: int = 30,
        cache_dir: str | Path = ".cache/sec/companyfacts",
    ) -> None:

        self.user_agent = (
            user_agent
            or "ATLAS Investment Research contact@example.com"
        )

        self.timeout = timeout
        self.cache_dir = Path(cache_dir)

    def fetch(
        self,
        cik: int,
    ) -> dict[str, Any]:

        if cik <= 0:
            raise ValueError("CIK must be positive.")

        cache = (
            self.cache_dir
            / f"CIK{cik:010d}.json"
        )

        if cache.exists():
            try:
                return json.loads(
                    cache.read_text(
                        encoding="utf-8"
                    )
                )
            except (OSError, json.JSONDecodeError):
                pass

        url = self.BASE_URL.format(cik=cik)

        request = Request(
            url,
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
                f"SEC Company Facts HTTP error: {exc.code}"
            ) from exc

        except URLError as exc:
            raise RuntimeError(
                f"SEC Company Facts network error: {exc.reason}"
            ) from exc

        payload = json.loads(
            raw.decode(
                "utf-8",
                errors="replace",
            )
        )

        cache.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        cache.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return payload

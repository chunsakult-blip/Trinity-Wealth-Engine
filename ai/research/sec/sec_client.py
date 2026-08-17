from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass
class SECResponse:
    url: str
    status_code: int
    payload: dict[str, Any]
    saved_file: str | None = None


class SECClient:
    """
    SEC Company Facts API client.

    Responsible only for:
    - HTTP communication
    - retry
    - raw response persistence

    Financial interpretation belongs to normalizer.
    """

    BASE_URL = "https://data.sec.gov"

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: int = 20,
        retry: int = 3,
        raw_dir: str = ".data/sec/raw",
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.retry = retry
        self.raw_dir = Path(raw_dir)

        self.raw_dir.mkdir(
            parents=True,
            exist_ok=True,
        )


    def _headers(self):
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }


    def get_company_facts(
        self,
        cik: str | int,
    ) -> SECResponse:

        cik_number = str(cik).zfill(10)

        url = (
            f"{self.BASE_URL}/api/xbrl/companyfacts/"
            f"CIK{cik_number}.json"
        )


        last_error = None


        for attempt in range(
            1,
            self.retry + 1,
        ):

            try:

                response = requests.get(
                    url,
                    headers=self._headers(),
                    timeout=self.timeout,
                )

                response.raise_for_status()


                payload = response.json()


                filename = (
                    self.raw_dir
                    /
                    f"CIK{cik_number}.json"
                )


                filename.write_text(
                    json.dumps(
                        payload,
                        indent=2,
                    ),
                    encoding="utf-8",
                )


                return SECResponse(
                    url=url,
                    status_code=response.status_code,
                    payload=payload,
                    saved_file=str(filename),
                )


            except Exception as exc:

                last_error = exc

                if attempt < self.retry:
                    time.sleep(
                        attempt * 2
                    )


        raise RuntimeError(
            f"SEC request failed: {last_error}"
        )

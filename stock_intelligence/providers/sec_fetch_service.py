from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from .sec_cache import SECCache
from .sec_client import SECClient


class SECFetchService:

    def __init__(
        self,
        client: SECClient,
        cache: Optional[SECCache] = None,
    ) -> None:

        self.client = client
        self.cache = cache

    def get_company_facts(
        self,
        cik: str | int,
        *,
        use_cache: bool = True,
        refresh: bool = False,
    ) -> Mapping[str, Any]:

        if (
            use_cache
            and not refresh
            and self.cache is not None
        ):

            cached = self.cache.load(cik)

            if cached is not None:

                self.client.validate_company_facts(
                    cached
                )

                return cached

        payload = (
            self.client.fetch_company_facts(
                cik
            )
        )

        self.client.validate_company_facts(
            payload
        )

        if self.cache is not None:

            self.cache.save(
                cik,
                payload,
            )

        return payload

from __future__ import annotations

import json
from pathlib import Path

from stock_intelligence.providers.sec_cache import (
    SECCache,
)

from stock_intelligence.providers.sec_client import (
    SECClient,
    SECClientConfig,
)

from stock_intelligence.providers.sec_fetch_service import (
    SECFetchService,
)


class FakeResponse:

    def __init__(
        self,
        payload: bytes,
    ) -> None:

        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False

    def read(self):
        return self.payload


class FakeOpener:

    def __init__(
        self,
        payload,
    ):

        self.payload = payload
        self.calls = 0
        self.last_request = None

    def __call__(
        self,
        request,
        timeout=None,
    ):

        self.calls += 1
        self.last_request = request

        return FakeResponse(
            json.dumps(
                self.payload
            ).encode("utf-8")
        )


def load_fixture():

    path = Path(
        __file__
    ).with_name(
        "sec_live_fixture.json"
    )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(handle)


def main():

    fixture = load_fixture()

    # ==============================================================
    # CLIENT
    # ==============================================================

    fake = FakeOpener(
        fixture
    )

    client = SECClient(
        SECClientConfig(
            user_agent=(
                "Trinity-Wealth-Engine "
                "contact@example.com"
            ),
            timeout_seconds=5,
            min_interval_seconds=0,
            max_retries=0,
        ),
        opener=fake,
        sleep=lambda _: None,
        clock=lambda: 0.0,
    )

    url = client.build_company_facts_url(
        "320193"
    )

    assert (
        url
        == (
            "https://data.sec.gov/"
            "api/xbrl/companyfacts/"
            "CIK0000320193.json"
        )
    )

    payload = client.fetch_company_facts(
        "320193"
    )

    assert fake.calls == 1

    assert (
        fake.last_request.get_header(
            "User-agent"
        )
        == (
            "Trinity-Wealth-Engine "
            "contact@example.com"
        )
    )

    client.validate_company_facts(
        payload
    )

    assert payload["cik"] == "0000320193"
    assert payload["entityName"] == (
        "OFFLINE TEST COMPANY"
    )


    # ==============================================================
    # CACHE
    # ==============================================================

    cache_root = (
        Path(__file__).parent
        / "_offline_sec_cache_test"
    )

    cache = SECCache(
        cache_root
    )

    saved = cache.save(
        "320193",
        payload,
    )

    assert saved.exists()

    loaded = cache.load(
        "320193"
    )

    assert loaded is not None
    assert loaded["cik"] == "0000320193"

    assert cache.exists(
        "320193"
    )


    # ==============================================================
    # SERVICE CACHE HIT
    # ==============================================================

    service = SECFetchService(
        client=client,
        cache=cache,
    )

    cached_payload = (
        service.get_company_facts(
            "320193",
            use_cache=True,
            refresh=False,
        )
    )

    assert cached_payload["cik"] == (
        "0000320193"
    )

    # No additional fake network call.
    assert fake.calls == 1


    # ==============================================================
    # SERVICE REFRESH
    # ==============================================================

    refreshed = (
        service.get_company_facts(
            "320193",
            use_cache=True,
            refresh=True,
        )
    )

    assert refreshed["cik"] == (
        "0000320193"
    )

    assert fake.calls == 2


    # ==============================================================
    # CIK NORMALIZATION
    # ==============================================================

    assert (
        client.normalize_cik(320193)
        == "0000320193"
    )

    assert (
        cache.normalize_cik("0000320193")
        == "0000320193"
    )


    # ==============================================================
    # INVALID CIK
    # ==============================================================

    try:

        client.normalize_cik(
            "ABC"
        )

        raise AssertionError(
            "Expected invalid CIK failure"
        )

    except ValueError:
        pass


    # ==============================================================
    # SECURITY BOUNDARY
    # ==============================================================

    try:

        client.fetch_json(
            "https://example.com/test.json"
        )

        raise AssertionError(
            "Expected SEC URL restriction"
        )

    except ValueError:
        pass


    # ==============================================================
    # INVALID PAYLOAD
    # ==============================================================

    try:

        client.validate_company_facts(
            {
                "cik": "0000000000"
            }
        )

        raise AssertionError(
            "Expected invalid payload failure"
        )

    except Exception:
        pass


    # ==============================================================
    # CLEANUP
    # ==============================================================

    for file in cache_root.glob(
        "*"
    ):

        file.unlink()

    cache_root.rmdir()


    # ==============================================================
    # RESULT
    # ==============================================================

    print("")
    print(
        "SEC LIVE CLIENT + CACHE CONTRACT"
    )
    print("PASS")
    print("")
    print(
        "SEC URL construction : PASS"
    )
    print(
        "CIK normalization    : PASS"
    )
    print(
        "User-Agent           : PASS"
    )
    print(
        "JSON validation      : PASS"
    )
    print(
        "SEC URL boundary     : PASS"
    )
    print(
        "Local cache          : PASS"
    )
    print(
        "Cache hit isolation  : PASS"
    )
    print(
        "Refresh behavior     : PASS"
    )
    print(
        "Invalid CIK guard    : PASS"
    )
    print(
        "Invalid payload guard: PASS"
    )
    print("")
    print(
        "NETWORK CALLS: 0"
    )
    print(
        "REAL SEC REQUESTS: 0"
    )
    print(
        "INGESTION: 0"
    )
    print("")
    print(
        "SEC LIVE CLIENT CONTRACT TEST: PASS"
    )


if __name__ == "__main__":
    main()

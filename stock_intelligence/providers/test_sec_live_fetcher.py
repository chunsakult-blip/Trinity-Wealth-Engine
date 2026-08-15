from __future__ import annotations

from typing import Any, Mapping

from stock_intelligence.providers.sec_live_fetcher import (
    SECFetchResult,
    SECLiveFetcher,
)

from stock_intelligence.providers.sec_request_policy import (
    SECRequestPolicy,
    SECRequestPolicyError,
)

from stock_intelligence.providers.sec_response_validator import (
    SECResponseValidationError,
    validate_company_facts_response,
)


class OfflineFetcher(
    SECLiveFetcher
):

    def __init__(self):

        super().__init__(
            user_agent="NICK-V3-TEST test@example.com",
            policy=SECRequestPolicy(
                min_interval_seconds=0,
                timeout_seconds=1,
                max_retries=0,
            ),
        )

        self.calls = []

    def _get_json(
        self,
        *,
        url: str,
        endpoint: str,
    ) -> SECFetchResult:

        self.calls.append(
            {
                "url": url,
                "endpoint": endpoint,
            }
        )

        if endpoint == "companyfacts":

            payload = {
                "entityName": "TEST COMPANY",
                "cik": "0000123456",
                "facts": {
                    "us-gaap": {
                        "Revenue": {
                            "label": "Revenue",
                            "units": {
                                "USD": [
                                    {
                                        "fy": 2025,
                                        "fp": "FY",
                                        "form": "10-K",
                                        "val": 1000,
                                        "filed": "2026-01-01",
                                        "accn": "0000123456-26-000001",
                                        "start": "2025-01-01",
                                        "end": "2025-12-31",
                                    }
                                ]
                            },
                        }
                    }
                },
            }

        elif endpoint == "submissions":

            payload = {
                "name": "TEST COMPANY",
                "cik": "0000123456",
                "filings": {
                    "recent": {
                        "form": ["10-K"],
                        "accessionNumber": [
                            "0000123456-26-000001"
                        ],
                    }
                },
            }

        else:

            payload = {}

        return SECFetchResult(
            endpoint=endpoint,
            url=url,
            payload=payload,
            status_code=200,
        )


def main():

    # ==============================================================
    # CIK NORMALIZATION
    # ==============================================================

    fetcher = OfflineFetcher()

    assert (
        fetcher.companyfacts_url("123456")
        ==
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000123456.json"
    )

    assert (
        fetcher.companyfacts_url("CIK123456")
        ==
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000123456.json"
    )

    assert (
        fetcher.submissions_url("123456")
        ==
        "https://data.sec.gov/submissions/CIK0000123456.json"
    )

    print("CIK URL normalization : PASS")


    # ==============================================================
    # COMPANY FACTS
    # ==============================================================

    facts = fetcher.fetch_company_facts(
        "123456"
    )

    assert facts.status_code == 200
    assert facts.endpoint == "companyfacts"
    assert facts.payload["entityName"] == "TEST COMPANY"
    assert "facts" in facts.payload

    assert (
        facts.payload["facts"]
        ["us-gaap"]
        ["Revenue"]
        ["units"]
        ["USD"][0]["val"]
        == 1000
    )

    print("Company Facts fetch boundary : PASS")


    # ==============================================================
    # SUBMISSIONS
    # ==============================================================

    submissions = fetcher.fetch_submissions(
        "123456"
    )

    assert submissions.status_code == 200
    assert submissions.endpoint == "submissions"
    assert submissions.payload["name"] == "TEST COMPANY"

    print("Submissions fetch boundary : PASS")


    # ==============================================================
    # USER-AGENT GUARD
    # ==============================================================

    try:

        SECLiveFetcher(
            user_agent=""
        )

        raise AssertionError(
            "Expected User-Agent validation failure"
        )

    except SECRequestPolicyError:

        pass

    print("User-Agent policy : PASS")


    # ==============================================================
    # INVALID CIK
    # ==============================================================

    try:

        fetcher.companyfacts_url(
            "ABC"
        )

        raise AssertionError(
            "Expected invalid CIK failure"
        )

    except ValueError:

        pass

    print("CIK validation : PASS")


    # ==============================================================
    # RESPONSE VALIDATION
    # ==============================================================

    try:

        validate_company_facts_response(
            {
                "entityName": "TEST"
            }
        )

        raise AssertionError(
            "Expected response validation failure"
        )

    except SECResponseValidationError:

        pass

    print("Response validation : PASS")


    # ==============================================================
    # NETWORK ISOLATION
    # ==============================================================

    assert len(fetcher.calls) == 2

    print("Network isolation : PASS")
    print("")
    print("NETWORK CALLS: 0")
    print("LIVE HTTP REQUESTS: 0")
    print("INGESTION: 0")
    print("")
    print("SEC LIVE FETCH BOUNDARY TEST: PASS")


if __name__ == "__main__":
    main()

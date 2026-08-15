from __future__ import annotations

import json
from pathlib import Path

from stock_intelligence.providers.sec_concept_mapper import (
    SECConceptMapper,
)

from stock_intelligence.providers.sec_period_resolver import (
    SECPeriodResolver,
)

from stock_intelligence.providers.sec_unit_resolver import (
    SECUnitResolver,
)

from stock_intelligence.providers.sec_raw_facts_mapper import (
    SECRawFactsMapper,
)


def main():

    provider_dir = Path(__file__).resolve().parent

    fixture_path = (
        provider_dir
        / "sec_company_facts_fixture.json"
    )

    payload = json.loads(
        fixture_path.read_text(
            encoding="utf-8"
        )
    )


    # ==================================================================
    # CONCEPT MAPPER
    # ==================================================================

    mapper = SECConceptMapper()

    assert mapper.canonical_field(
        "Revenues"
    ) == "revenue"

    assert mapper.canonical_field(
        "NetIncomeLoss"
    ) == "net_income"

    assert mapper.canonical_field(
        "Assets"
    ) == "assets"

    assert mapper.canonical_field(
        "DefinitelyUnknown"
    ) is None


    # ==================================================================
    # PERIOD RESOLVER
    # ==================================================================

    observation = {
        "fy": 2025,
        "fp": "FY",
        "form": "10-K",
        "filed": "2026-01-15",
        "end": "2025-12-31",
    }

    assert (
        SECPeriodResolver.fiscal_period(
            observation
        )
        == "FY2025-FY"
    )

    assert SECPeriodResolver.is_annual(
        observation
    )

    assert (
        SECPeriodResolver.observation_date(
            observation
        ).isoformat()
        == "2026-01-15"
    )


    # ==================================================================
    # UNIT RESOLVER
    # ==================================================================

    usd_observation = {
        "unit": "USD",
        "val": 1000,
    }

    assert SECUnitResolver.supported(
        usd_observation
    )

    assert (
        SECUnitResolver.normalize_value(
            usd_observation
        )
        == 1000.0
    )

    shares_observation = {
        "unit": "shares",
        "val": 100,
    }

    assert SECUnitResolver.supported(
        shares_observation
    )


    # ==================================================================
    # RAW FACTS MAPPER
    # ==================================================================

    raw_mapper = SECRawFactsMapper()

    records = raw_mapper.map_payload(
        ticker="TEST",
        payload=payload,
    )

    assert len(records) == 1

    record = records[0]

    assert record["fiscal_period"] == (
        "FY2025-FY"
    )

    assert record["revenue"] == 1000.0
    assert record["gross_profit"] == 500.0
    assert record["operating_income"] == 200.0
    assert record["net_income"] == 100.0

    assert record["ocf"] == 150.0
    assert record["capex"] == -50.0

    assert record["cash"] == 200.0
    assert record["debt"] == 300.0

    assert record["assets"] == 1200.0
    assert record["equity"] == 600.0

    assert record["shares"] == 100.0


    # ==================================================================
    # PROVENANCE
    # ==================================================================

    provenance = record[
        "_provenance"
    ]

    assert len(provenance) >= 10

    revenue_provenance = [
        item
        for item in provenance
        if item["field"] == "revenue"
    ]

    assert len(
        revenue_provenance
    ) == 1

    revenue = revenue_provenance[0]

    assert revenue["source"] == "SEC"
    assert revenue["accession"] == (
        "0000000000-26-000001"
    )
    assert revenue["form"] == "10-K"
    assert revenue["unit"] == "USD"


    # ==================================================================
    # UNKNOWN CONCEPTS MUST BE IGNORED
    # ==================================================================

    payload["facts"]["us-gaap"][
        "RandomUnknownConcept"
    ] = {
        "units": {
            "USD": [
                {
                    "fy": 2025,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2026-01-15",
                    "val": 999999,
                }
            ]
        }
    }

    records_unknown = (
        raw_mapper.map_payload(
            ticker="TEST",
            payload=payload,
        )
    )

    assert (
        "random_unknown_concept"
        not in records_unknown[0]
    )

    assert (
        records_unknown[0].get(
            "RandomUnknownConcept"
        )
        is None
    )


    # ==================================================================
    # NETWORK ISOLATION
    # ==================================================================

    import inspect

    source_modules = [
        SECConceptMapper,
        SECPeriodResolver,
        SECUnitResolver,
        SECRawFactsMapper,
    ]

    forbidden = [
        "requests.",
        "httpx.",
        "urllib.request",
        "urlopen(",
        "http://",
        "https://",
    ]

    for module in source_modules:

        source = inspect.getsource(
            module
        )

        for term in forbidden:
            assert term not in source


    # ==================================================================
    # FINAL
    # ==================================================================

    print("")
    print("SEC RAW COMPANY FACTS MAPPER CONTRACT")
    print("PASS")
    print("")
    print("Concept mapping       : PASS")
    print("Period resolution     : PASS")
    print("Unit resolution       : PASS")
    print("Canonical raw fields  : PASS")
    print("Provenance extraction : PASS")
    print("Unknown concept guard : PASS")
    print("Network isolation     : PASS")
    print("")
    print("NETWORK CALLS: 0")
    print("INGESTION: 0")
    print("")
    print("SEC RAW FACTS MAPPER TEST: PASS")


if __name__ == "__main__":
    main()

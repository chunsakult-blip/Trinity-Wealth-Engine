from __future__ import annotations

from stock_intelligence.providers.financial_model import (
    FinancialPeriod,
    FinancialProvenance,
    NormalizedFinancials,
)

from stock_intelligence.providers.sec_normalization_bridge import (
    SECNormalizationBridge,
    normalize_sec_dataset,
    normalize_sec_period,
)


def main():

    bridge = SECNormalizationBridge()


    # ==================================================================
    # 1. SINGLE SEC PERIOD
    # ==================================================================

    period = bridge.normalize_period(
        ticker="AAPL",
        fiscal_period="FY2025",
        raw={
            "revenue": 1000,
            "gross_profit": 500,
            "operating_income": 200,
            "net_income": 100,
            "ocf": 150,
            "capex": -50,
            "cash": 200,
            "debt": 300,
            "assets": 1200,
            "equity": 600,
            "shares": 100,
        },
        source_url="offline://sec/companyfacts",
        accession="OFFLINE-AAPL-2025",
        retrieved_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(
        period,
        FinancialPeriod,
    )

    assert period.ticker == "AAPL"
    assert period.fiscal_period == "FY2025"

    assert period.revenue == 1000.0
    assert period.fcf == 100.0

    assert abs(
        period.roe - (100 / 600)
    ) < 1e-12

    assert abs(
        period.roa - (100 / 1200)
    ) < 1e-12

    assert period.net_debt == 100.0


    # ==================================================================
    # 2. PROVENANCE MUST SURVIVE SEC -> NORMALIZATION
    # ==================================================================

    revenue_records = [
        item
        for item in period.provenance
        if item.field == "revenue"
    ]

    assert len(revenue_records) == 1

    revenue = revenue_records[0]

    assert isinstance(
        revenue,
        FinancialProvenance,
    )

    assert revenue.source == "SEC"
    assert revenue.source_url == "offline://sec/companyfacts"
    assert revenue.accession == "OFFLINE-AAPL-2025"

    assert revenue.raw_value == 1000
    assert revenue.normalized_value == 1000.0


    # ==================================================================
    # 3. MULTI-PERIOD SEC DATASET
    # ==================================================================

    raw_periods = [
        {
            "fiscal_period": "FY2024",
            "revenue": 800,
            "net_income": 80,
            "assets": 800,
            "equity": 400,
            "cash": 100,
            "debt": 200,
        },
        {
            "fiscal_period": "FY2025",
            "revenue": 1000,
            "net_income": 100,
            "assets": 1200,
            "equity": 600,
            "cash": 200,
            "debt": 300,
        },
    ]

    dataset = bridge.normalize_dataset(
        "AAPL",
        raw_periods,
    )

    assert isinstance(
        dataset,
        NormalizedFinancials,
    )

    assert dataset.ticker == "AAPL"
    assert len(dataset.periods) == 2


    fy2024 = dataset.get_period("FY2024")
    fy2025 = dataset.get_period("FY2025")

    assert fy2024 is not None
    assert fy2025 is not None

    assert fy2024.equity == 400.0
    assert fy2025.equity == 600.0

    assert abs(
        fy2024.roe - (80 / 400)
    ) < 1e-12

    assert abs(
        fy2025.roe - (100 / 600)
    ) < 1e-12


    # ==================================================================
    # 4. FUNCTION API
    # ==================================================================

    direct_period = normalize_sec_period(
        ticker="MSFT",
        fiscal_period="FY2025",
        raw={
            "revenue": 2000,
            "net_income": 200,
            "assets": 2000,
            "equity": 1000,
        },
        source_url="offline://sec",
        accession="OFFLINE-MSFT-2025",
    )

    assert isinstance(
        direct_period,
        FinancialPeriod,
    )

    assert direct_period.revenue == 2000.0


    direct_dataset = normalize_sec_dataset(
        "MSFT",
        [
            {
                "fiscal_period": "FY2025",
                "revenue": 2000,
                "net_income": 200,
                "assets": 2000,
                "equity": 1000,
            }
        ],
    )

    assert isinstance(
        direct_dataset,
        NormalizedFinancials,
    )

    assert len(direct_dataset.periods) == 1


    # ==================================================================
    # 5. NO NETWORK CONTRACT
    # ==================================================================

    # The bridge accepts already retrieved SEC data only.
    # There is intentionally no requests/httpx/urllib invocation here.

    import inspect

    bridge_source = inspect.getsource(
        SECNormalizationBridge
    )

    forbidden_network_terms = [
        "requests.",
        "httpx.",
        "urllib.request",
        "urlopen(",
        "http://",
        "https://",
    ]

    for term in forbidden_network_terms:
        assert term not in bridge_source


    # ==================================================================
    # FINAL
    # ==================================================================

    print("")
    print("SEC -> NORMALIZATION INTEGRATION CONTRACT")
    print("PASS")
    print("")
    print("SECNormalizationBridge : PASS")
    print("Single-period mapping  : PASS")
    print("Multi-period mapping   : PASS")
    print("Canonical model        : PASS")
    print("Provenance preservation : PASS")
    print("Function API           : PASS")
    print("Network isolation      : PASS")
    print("")
    print("NETWORK CALLS: 0")
    print("INGESTION: 0")
    print("")
    print("SEC NORMALIZATION BRIDGE TEST: PASS")


if __name__ == "__main__":
    main()

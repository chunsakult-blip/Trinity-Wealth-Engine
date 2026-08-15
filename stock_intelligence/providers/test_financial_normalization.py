from __future__ import annotations

from stock_intelligence.providers.financial_model import (
    FinancialPeriod,
    FinancialProvenance,
    NormalizedFinancials,
)

from stock_intelligence.providers.financial_normalization import (
    normalize_financial_period,
    normalize_financials,
)


def main():

    # ==============================================================
    # FY2025
    # ==============================================================

    p2025 = normalize_financial_period(
        ticker="TEST",
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
        },
        source="SEC",
        source_url="offline://test",
        accession="TEST-2025",
        retrieved_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(p2025, FinancialPeriod)

    assert p2025.revenue == 1000.0
    assert p2025.fcf == 100.0

    assert abs(p2025.roe - (100 / 600)) < 1e-12
    assert abs(p2025.roa - (100 / 1200)) < 1e-12

    assert abs(
        p2025.gross_margin - 0.5
    ) < 1e-12

    assert abs(
        p2025.operating_margin - 0.2
    ) < 1e-12

    assert abs(
        p2025.net_margin - 0.1
    ) < 1e-12

    assert p2025.net_debt == 100.0

    assert abs(
        p2025.debt_to_equity - 0.5
    ) < 1e-12

    assert p2025.roic is not None

    assert len(p2025.provenance) > 0

    assert all(
        isinstance(item, FinancialProvenance)
        for item in p2025.provenance
    )


    # ==============================================================
    # PROVENANCE CHECK
    # ==============================================================

    revenue_provenance = [
        item
        for item in p2025.provenance
        if item.field == "revenue"
    ]

    assert len(revenue_provenance) == 1

    revenue_record = revenue_provenance[0]

    assert revenue_record.ticker == "TEST"
    assert revenue_record.period == "FY2025"
    assert revenue_record.source == "SEC"
    assert revenue_record.source_url == "offline://test"
    assert revenue_record.accession == "TEST-2025"
    assert revenue_record.raw_value == 1000
    assert revenue_record.normalized_value == 1000.0


    # ==============================================================
    # FY2024
    #
    # Deliberately different denominators.
    # ==============================================================
    
    p2024 = normalize_financial_period(
        ticker="TEST",
        fiscal_period="FY2024",
        raw={
            "revenue": 800,
            "operating_income": 120,
            "net_income": 80,
            "cash": 100,
            "debt": 200,
            "assets": 800,
            "equity": 400,
        },
        source="SEC",
    )

    assert isinstance(p2024, FinancialPeriod)

    assert abs(
        p2024.roe - (80 / 400)
    ) < 1e-12

    assert abs(
        p2024.roa - (80 / 800)
    ) < 1e-12

    # Must NOT reuse FY2025 denominators.
    assert p2024.roe != p2025.roe
    assert p2024.roa != p2025.roa


    # ==============================================================
    # MULTI-PERIOD DATASET
    # ==============================================================

    dataset = normalize_financials(
        "TEST",
        [
            {
                "fiscal_period": "FY2024",
                "net_income": 80,
                "assets": 800,
                "equity": 400,
            },
            {
                "fiscal_period": "FY2025",
                "net_income": 100,
                "assets": 1200,
                "equity": 600,
            },
        ],
    )

    assert isinstance(
        dataset,
        NormalizedFinancials,
    )

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


    # ==============================================================
    # ROIC
    # ==============================================================

    roic_period = normalize_financial_period(
        ticker="TEST",
        fiscal_period="FY2025",
        raw={
            "operating_income": 200,
            "tax_rate": 0.20,
            "equity": 600,
            "debt": 300,
            "cash": 200,
        },
        source="SEC",
    )

    # NOPAT
    # = 200 * (1 - 0.20)
    # = 160
    #
    # Invested Capital
    # = 600 + 300 - 200
    # = 700
    #
    # ROIC
    # = 160 / 700

    assert abs(
        roic_period.roic - (160 / 700)
    ) < 1e-12


    # ==============================================================
    # FCF EXPLICIT VALUE
    # ==============================================================

    explicit_fcf = normalize_financial_period(
        ticker="TEST",
        fiscal_period="FY2025",
        raw={
            "ocf": 250,
            "capex": -100,
            "fcf": 123,
        },
        source="SEC",
    )

    assert explicit_fcf.fcf == 123.0


    # ==============================================================
    # FCF DERIVED VALUE
    # ==============================================================

    derived_fcf = normalize_financial_period(
        ticker="TEST",
        fiscal_period="FY2025",
        raw={
            "ocf": 250,
            "capex": -100,
        },
        source="SEC",
    )

    assert derived_fcf.fcf == 150.0


    # ==============================================================
    # ZERO-DENOMINATOR SAFETY
    # ==============================================================

    zero_denominator = normalize_financial_period(
        ticker="TEST",
        fiscal_period="FY2025",
        raw={
            "net_income": 100,
            "equity": 0,
            "assets": 0,
            "revenue": 0,
        },
        source="SEC",
    )

    assert zero_denominator.roe is None
    assert zero_denominator.roa is None
    assert zero_denominator.net_margin is None


    # ==============================================================
    # BOOLEAN INPUT SAFETY
    # ==============================================================

    boolean_input = normalize_financial_period(
        ticker="TEST",
        fiscal_period="FY2025",
        raw={
            "revenue": True,
            "net_income": False,
        },
        source="SEC",
    )

    assert boolean_input.revenue is None
    assert boolean_input.net_income is None


    # ==============================================================
    # MISSING FISCAL PERIOD MUST FAIL
    # ==============================================================

    try:

        normalize_financials(
            "TEST",
            [
                {
                    "net_income": 100,
                }
            ],
        )

        raise AssertionError(
            "Expected ValueError for missing fiscal_period"
        )

    except ValueError as exc:

        assert "fiscal_period" in str(exc)


    # ==============================================================
    # FINAL RESULT
    # ==============================================================

    print("")
    print("SEC / FUNDAMENTAL NORMALIZATION CONTRACT")
    print("PASS")
    print("")
    print("Canonical Financial Model : PASS")
    print("Per-period ROE            : PASS")
    print("Per-period ROA            : PASS")
    print("ROIC                      : PASS")
    print("FCF                       : PASS")
    print("Margins                   : PASS")
    print("Net Debt                  : PASS")
    print("Provenance                : PASS")
    print("Multi-period              : PASS")
    print("Zero-denominator safety   : PASS")
    print("Boolean input safety      : PASS")
    print("Fiscal-period validation  : PASS")
    print("")
    print("NETWORK CALLS: 0")
    print("INGESTION: 0")
    print("")
    print("NORMALIZATION CONTRACT TEST: PASS")


if __name__ == "__main__":
    main()

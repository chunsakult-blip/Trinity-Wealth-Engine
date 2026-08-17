from __future__ import annotations

from ai.research.financial.normalizer import (
    FinancialFactNormalizer,
)


def _duration_fact(
    value: float,
    start: str,
    end: str,
    *,
    filed: str = "2026-01-01",
    form: str = "10-Q",
    fp: str = "Q1",
) -> dict:
    return {
        "val": value,
        "start": start,
        "end": end,
        "filed": filed,
        "form": form,
        "fp": fp,
    }


def _instant_fact(
    value: float,
    end: str,
    *,
    filed: str = "2026-01-01",
) -> dict:
    return {
        "val": value,
        "end": end,
        "filed": filed,
        "form": "10-Q",
        "fp": "Q1",
    }


def _four_quarter_payload() -> dict:
    quarters = [
        {
            "start": "2025-01-01",
            "end": "2025-03-31",
            "revenue": 100,
            "net_income": 10,
            "ocf": 30,
            "capex": -5,
            "interest": 2,
            "fp": "Q1",
        },
        {
            "start": "2025-04-01",
            "end": "2025-06-30",
            "revenue": 110,
            "net_income": 11,
            "ocf": 31,
            "capex": -6,
            "interest": 3,
            "fp": "Q2",
        },
        {
            "start": "2025-07-01",
            "end": "2025-09-30",
            "revenue": 120,
            "net_income": 12,
            "ocf": 32,
            "capex": -7,
            "interest": 4,
            "fp": "Q3",
        },
        {
            "start": "2025-10-01",
            "end": "2025-12-31",
            "revenue": 130,
            "net_income": 13,
            "ocf": 33,
            "capex": -8,
            "interest": 5,
            "fp": "Q4",
        },
    ]

    revenue = []
    net_income = []
    ocf = []
    capex = []
    interest = []

    assets = []
    equity = []
    cash = []
    debt = []

    for q in quarters:
        fact = {
            "start": q["start"],
            "end": q["end"],
            "filed": "2026-01-01",
            "form": "10-Q",
            "fp": q["fp"],
        }

        revenue.append({
            **fact,
            "val": q["revenue"],
        })

        net_income.append({
            **fact,
            "val": q["net_income"],
        })

        ocf.append({
            **fact,
            "val": q["ocf"],
        })

        capex.append({
            **fact,
            "val": q["capex"],
        })

        interest.append({
            **fact,
            "val": q["interest"],
        })

    # Instant values deliberately differ by quarter.
    # TTM must use the latest quarter only.
    for end, a, e, c, d in [
        ("2025-03-31", 1000, 500, 100, 300),
        ("2025-06-30", 1100, 550, 110, 320),
        ("2025-09-30", 1200, 600, 120, 340),
        ("2025-12-31", 1400, 700, 150, 400),
    ]:
        assets.append(_instant_fact(a, end))
        equity.append(_instant_fact(e, end))
        cash.append(_instant_fact(c, end))
        debt.append(_instant_fact(d, end))

    return {
        "entityName": "TTM Test Corp",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": revenue}
                },
                "NetIncomeLoss": {
                    "units": {"USD": net_income}
                },
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {"USD": ocf}
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {"USD": capex}
                },
                "InterestExpenseNonOperating": {
                    "units": {"USD": interest}
                },
                "Assets": {
                    "units": {"USD": assets}
                },
                "StockholdersEquity": {
                    "units": {"USD": equity}
                },
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {"USD": cash}
                },
                "LongTermDebtNoncurrent": {
                    "units": {"USD": debt}
                },
            }
        },
    }


def test_true_ttm_sums_latest_four_quarters():
    result = FinancialFactNormalizer().normalize(
        _four_quarter_payload(),
        cik=999001,
        ticker="TTM",
    )

    assert result.ttm is not None

    ttm = result.ttm

    assert ttm.period == "TTM:2025-12-31"
    assert ttm.start == "2025-01-01"
    assert ttm.end == "2025-12-31"

    # Duration metrics are summed.
    assert ttm.revenue == 460
    assert ttm.net_income == 46
    assert ttm.operating_cash_flow == 126
    assert ttm.capex == 26
    assert ttm.interest_expense == 14

    # FCF = TTM OCF - TTM CapEx.
    assert ttm.free_cash_flow == 100

    # Instant metrics come from the latest quarter only.
    assert ttm.assets == 1400
    assert ttm.equity == 700
    assert ttm.cash == 150
    assert ttm.debt == 400


def test_true_ttm_annual_period_is_used_directly():
    payload = {
        "entityName": "Annual TTM Test Corp",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "val": 1200,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "val": 180,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "val": 3000,
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },
            }
        },
    }

    result = FinancialFactNormalizer().normalize(
        payload,
        cik=999002,
        ticker="ANN",
    )

    assert result.ttm is not None
    assert result.ttm.period == "TTM:2025-12-31"
    assert result.ttm.start == "2025-01-01"
    assert result.ttm.end == "2025-12-31"

    assert result.ttm.revenue == 1200
    assert result.ttm.net_income == 180
    assert result.ttm.assets == 3000


def test_true_ttm_requires_four_quarters():
    payload = _four_quarter_payload()

    revenue_units = payload["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"]

    # Remove the oldest quarter.
    revenue_units.pop(0)

    net_income_units = payload["facts"]["us-gaap"][
        "NetIncomeLoss"
    ]["units"]["USD"]
    net_income_units.pop(0)

    ocf_units = payload["facts"]["us-gaap"][
        "NetCashProvidedByUsedInOperatingActivities"
    ]["units"]["USD"]
    ocf_units.pop(0)

    capex_units = payload["facts"]["us-gaap"][
        "PaymentsToAcquirePropertyPlantAndEquipment"
    ]["units"]["USD"]
    capex_units.pop(0)

    interest_units = payload["facts"]["us-gaap"][
        "InterestExpenseNonOperating"
    ]["units"]["USD"]
    interest_units.pop(0)

    result = FinancialFactNormalizer().normalize(
        payload,
        cik=999003,
        ticker="THREE",
    )

    assert result.ttm is None

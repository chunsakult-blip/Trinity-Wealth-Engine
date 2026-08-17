from __future__ import annotations

from ai.research.financial.normalizer import (
    FinancialFactNormalizer,
)


def _duration(
    value: float,
    start: str,
    end: str,
    *,
    filed: str = "2026-11-01",
    form: str = "10-Q",
    fp: str = "Q3",
) -> dict:
    return {
        "val": value,
        "start": start,
        "end": end,
        "filed": filed,
        "form": form,
        "fp": fp,
    }


def _instant(
    value: float,
    end: str,
    *,
    filed: str = "2026-11-01",
) -> dict:
    return {
        "val": value,
        "end": end,
        "filed": filed,
        "form": "10-Q",
        "fp": "Q3",
    }


def _sec_ytd_payload() -> dict:
    """
    SEC-style structure:

    Prior FY:
        2025-01-01 -> 2025-12-31

    Prior YTD:
        2025-01-01 -> 2025-09-30

    Current YTD:
        2026-01-01 -> 2026-09-30

    Expected TTM:

        Prior FY - Prior YTD + Current YTD
    """

    return {
        "entityName": "SEC YTD Test Corp",
        "facts": {
            "us-gaap": {

                # ----------------------------------------------------
                # Revenue
                # ----------------------------------------------------

                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [

                            # Prior FY = 1000
                            _duration(
                                1000,
                                "2025-01-01",
                                "2025-12-31",
                                filed="2026-02-15",
                                form="10-K",
                                fp="FY",
                            ),

                            # Prior YTD = 700
                            _duration(
                                700,
                                "2025-01-01",
                                "2025-09-30",
                                filed="2025-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),

                            # Current YTD = 800
                            _duration(
                                800,
                                "2026-01-01",
                                "2026-09-30",
                                filed="2026-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),
                        ]
                    }
                },

                # ----------------------------------------------------
                # Net Income
                # ----------------------------------------------------

                "NetIncomeLoss": {
                    "units": {
                        "USD": [

                            # Prior FY = 200
                            _duration(
                                200,
                                "2025-01-01",
                                "2025-12-31",
                                filed="2026-02-15",
                                form="10-K",
                                fp="FY",
                            ),

                            # Prior YTD = 140
                            _duration(
                                140,
                                "2025-01-01",
                                "2025-09-30",
                                filed="2025-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),

                            # Current YTD = 170
                            _duration(
                                170,
                                "2026-01-01",
                                "2026-09-30",
                                filed="2026-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),
                        ]
                    }
                },

                # ----------------------------------------------------
                # Operating Cash Flow
                # ----------------------------------------------------

                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [

                            # Prior FY = 300
                            _duration(
                                300,
                                "2025-01-01",
                                "2025-12-31",
                                filed="2026-02-15",
                                form="10-K",
                                fp="FY",
                            ),

                            # Prior YTD = 210
                            _duration(
                                210,
                                "2025-01-01",
                                "2025-09-30",
                                filed="2025-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),

                            # Current YTD = 260
                            _duration(
                                260,
                                "2026-01-01",
                                "2026-09-30",
                                filed="2026-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),
                        ]
                    }
                },

                # ----------------------------------------------------
                # CapEx
                #
                # SEC cash outflow is negative.
                # Normalizer canonicalizes CapEx to positive.
                # ----------------------------------------------------

                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {
                        "USD": [

                            # Prior FY = -100
                            _duration(
                                -100,
                                "2025-01-01",
                                "2025-12-31",
                                filed="2026-02-15",
                                form="10-K",
                                fp="FY",
                            ),

                            # Prior YTD = -70
                            _duration(
                                -70,
                                "2025-01-01",
                                "2025-09-30",
                                filed="2025-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),

                            # Current YTD = -90
                            _duration(
                                -90,
                                "2026-01-01",
                                "2026-09-30",
                                filed="2026-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),
                        ]
                    }
                },

                # ----------------------------------------------------
                # Interest Expense
                # ----------------------------------------------------

                "InterestExpenseNonOperating": {
                    "units": {
                        "USD": [

                            # Prior FY = 40
                            _duration(
                                40,
                                "2025-01-01",
                                "2025-12-31",
                                filed="2026-02-15",
                                form="10-K",
                                fp="FY",
                            ),

                            # Prior YTD = 30
                            _duration(
                                30,
                                "2025-01-01",
                                "2025-09-30",
                                filed="2025-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),

                            # Current YTD = 35
                            _duration(
                                35,
                                "2026-01-01",
                                "2026-09-30",
                                filed="2026-11-01",
                                form="10-Q",
                                fp="Q3",
                            ),
                        ]
                    }
                },

                # ----------------------------------------------------
                # Instant metrics
                #
                # These must come from latest balance-sheet period.
                # ----------------------------------------------------

                "Assets": {
                    "units": {
                        "USD": [
                            _instant(1000, "2025-12-31"),
                            _instant(1200, "2026-09-30"),
                        ]
                    }
                },

                "StockholdersEquity": {
                    "units": {
                        "USD": [
                            _instant(500, "2025-12-31"),
                            _instant(650, "2026-09-30"),
                        ]
                    }
                },

                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {
                        "USD": [
                            _instant(100, "2025-12-31"),
                            _instant(180, "2026-09-30"),
                        ]
                    }
                },

                "LongTermDebtNoncurrent": {
                    "units": {
                        "USD": [
                            _instant(300, "2025-12-31"),
                            _instant(420, "2026-09-30"),
                        ]
                    }
                },
            }
        },
    }


def test_sec_ytd_true_ttm_derivation():
    result = FinancialFactNormalizer().normalize(
        _sec_ytd_payload(),
        cik=999101,
        ticker="SECYTD",
    )

    assert result.ttm is not None

    ttm = result.ttm

    assert ttm.period == "TTM:2026-09-30"
    assert ttm.end == "2026-09-30"

    # --------------------------------------------------------
    # TRUE TTM = Prior FY - Prior YTD + Current YTD
    # --------------------------------------------------------

    assert ttm.revenue == 1100
    assert ttm.net_income == 230
    assert ttm.operating_cash_flow == 350

    # Canonical CapEx:
    #
    # FY      -100
    # Prior   -70
    # Current -90
    #
    # TTM cash outflow = -100 - (-70) + (-90)
    #                  = -120
    #
    # Normalizer stores CapEx as positive outflow.
    assert ttm.capex == 120

    assert ttm.interest_expense == 45

    # FCF = OCF - CapEx
    assert ttm.free_cash_flow == 230


def test_sec_ytd_uses_latest_balance_sheet_values():
    result = FinancialFactNormalizer().normalize(
        _sec_ytd_payload(),
        cik=999102,
        ticker="SECBS",
    )

    assert result.ttm is not None

    ttm = result.ttm

    # Instant metrics MUST NOT be summed.
    assert ttm.assets == 1200
    assert ttm.equity == 650
    assert ttm.cash == 180
    assert ttm.debt == 420


def test_sec_ytd_does_not_sum_ytd_periods_directly():
    result = FinancialFactNormalizer().normalize(
        _sec_ytd_payload(),
        cik=999103,
        ticker="SECSUM",
    )

    assert result.ttm is not None

    ttm = result.ttm

    # Wrong implementation would produce:
    #
    # 700 + 800 = 1500
    #
    # Correct TTM:
    #
    # 1000 - 700 + 800 = 1100
    assert ttm.revenue == 1100

    assert ttm.revenue != 1500


def test_sec_ytd_requires_prior_year_ytd():
    payload = _sec_ytd_payload()

    revenue = payload["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"]

    # Remove prior-year YTD.
    revenue.pop(1)

    result = FinancialFactNormalizer().normalize(
        payload,
        cik=999104,
        ticker="SECFAIL",
    )

    # The normalizer must never fabricate TTM.
    assert result.ttm is None

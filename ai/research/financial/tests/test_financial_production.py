from __future__ import annotations

from ai.research.financial.engine import (
    FinancialIntelligenceEngine,
)
from ai.research.financial.metrics import (
    FinancialMetricsEngine,
)
from ai.research.financial.models import (
    FinancialPeriod,
    NormalizedFinancials,
)
from ai.research.financial.normalizer import (
    FinancialFactNormalizer,
)
from ai.research.financial.quality import (
    FinancialQualityEngine,
)


def make_payload() -> dict:

    return {
        "entityName": "ATLAS Test Corp",
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
                            },
                            {
                                "val": 1000,
                                "start": "2024-01-01",
                                "end": "2024-12-31",
                                "filed": "2025-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            },
                        ]
                    }
                },

                "GrossProfit": {
                    "units": {
                        "USD": [
                            {
                                "val": 600,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },

                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "val": 240,
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
                            },
                            {
                                "val": 150,
                                "start": "2024-01-01",
                                "end": "2024-12-31",
                                "filed": "2025-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            },
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

                "StockholdersEquity": {
                    "units": {
                        "USD": [
                            {
                                "val": 1500,
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },

                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {
                        "USD": [
                            {
                                "val": 500,
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },

                "LongTermDebtNoncurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 700,
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },

                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            {
                                "val": 300,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },

                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {
                        "USD": [
                            {
                                "val": -100,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },

                "InterestExpenseNonOperating": {
                    "units": {
                        "USD": [
                            {
                                "val": 30,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                },

                "IncomeTaxExpenseBenefit": {
                    "units": {
                        "USD": [
                            {
                                "val": 60,
                                "start": "2025-01-01",
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


def test_normalizer_builds_periods():

    result = FinancialFactNormalizer().normalize(
        make_payload(),
        cik=123456,
        ticker="TEST",
    )

    assert result.latest_period is not None
    assert result.prior_period is not None

    assert result.latest_period.revenue == 1200
    assert result.latest_period.net_income == 180

    # CapEx canonicalized to positive outflow.
    assert result.latest_period.capex == 100

    # FCF = OCF - positive CapEx.
    assert result.latest_period.free_cash_flow == 200


def test_growth_metrics():

    result = FinancialFactNormalizer().normalize(
        make_payload(),
        cik=123456,
        ticker="TEST",
    )

    assert round(
        result.metrics["revenue_growth"],
        6,
    ) == round(
        0.20,
        6,
    )

    assert round(
        result.metrics["net_income_growth"],
        6,
    ) == round(
        0.20,
        6,
    )


def test_metrics_engine():

    financials = FinancialFactNormalizer().normalize(
        make_payload(),
        cik=123456,
    )

    metrics = FinancialMetricsEngine().calculate(
        financials
    )

    assert metrics["gross_margin"] == 0.5
    assert metrics["operating_margin"] == 0.2
    assert metrics["net_margin"] == 0.15

    assert metrics["free_cash_flow"] == 200

    assert metrics["roe"] == 0.12

    assert metrics["debt_to_equity"] == (
        700 / 1500
    )

    assert metrics["net_debt"] == 200

    assert metrics["interest_coverage"] == 8


def test_quality_uses_derived_metrics():

    financials = FinancialFactNormalizer().normalize(
        make_payload(),
        cik=123456,
    )

    metrics = FinancialMetricsEngine().calculate(
        financials
    )

    financials.metrics.update(metrics)

    quality = FinancialQualityEngine().evaluate(
        financials
    )

    assert quality.score > 0
    assert quality.completeness > 0
    assert quality.consistency > 0

    assert financials.quality["score"] == (
        quality.score
    )


def test_models_contract():

    period = FinancialPeriod(
        period="2025",
        start="2025-01-01",
        end="2025-12-31",
        revenue=100,
    )

    financials = NormalizedFinancials(
        cik=1,
        ticker="TEST",
        company_name="Test",
        currency="USD",
        latest_period=period,
        prior_period=None,
        ttm=period,
    )

    assert financials.latest_period is period
    assert financials.ticker == "TEST"


def test_engine_pipeline(monkeypatch):

    engine = FinancialIntelligenceEngine()

    monkeypatch.setattr(
        engine.provider,
        "fetch",
        lambda cik: make_payload(),
    )

    result = engine.analyze_company(
        123456,
        ticker="TEST",
        company_name="ATLAS Test Corp",
    )

    assert result["status"] == "success"
    assert result["market"] == "US"
    assert result["stage"] == (
        "financial_intelligence"
    )

    assert result["metrics"]["revenue"] == 1200
    assert result["metrics"]["free_cash_flow"] == 200

    assert result["quality"]["score"] > 0
    assert result["quality"]["completeness"] > 0

    assert result["latest_period"] is not None
    assert result["prior_period"] is not None
    assert result["period_count"] >= 2

    assert result["evidence"]

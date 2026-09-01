import json
from pathlib import Path

import pytest

from ai.research.financial.normalizer import FinancialFactNormalizer


COMPANIES = {
    "AAPL": 320193,
    "MSFT": 789019,
    "NVDA": 1045810,
    "AMZN": 1018724,
    "GOOGL": 1652044,
    "META": 1326801,
    "JPM": 19617,
}


def project_root():
    return Path(__file__).resolve().parents[2]


def cache_path(cik):
    return (
        project_root()
        / ".cache"
        / "sec"
        / "companyfacts"
        / f"CIK{cik:010d}.json"
    )


def load_company(ticker, cik):
    path = cache_path(cik)

    if not path.exists():
        pytest.skip(f"{ticker} SEC cache not available: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    normalizer = FinancialFactNormalizer()

    result = normalizer.normalize(
        payload,
        cik=cik,
        ticker=ticker,
    )

    return result


@pytest.mark.parametrize(
    "ticker,cik",
    list(COMPANIES.items()),
)
def test_multi_company_ttm_exists(ticker, cik):
    result = load_company(ticker, cik)

    assert result is not None
    assert result.ttm is not None, f"{ticker}: TTM missing"
    assert result.ttm.revenue is not None, f"{ticker}: TTM revenue missing"

    assert result.ttm.revenue > 0, (
        f"{ticker}: TTM revenue must be positive, "
        f"got={result.ttm.revenue}"
    )


@pytest.mark.parametrize(
    "ticker,cik",
    list(COMPANIES.items()),
)
def test_multi_company_ttm_period_is_valid(ticker, cik):
    result = load_company(ticker, cik)

    if result.ttm is None:
        pytest.fail(f"{ticker}: TTM missing")

    assert result.ttm.start is not None
    assert result.ttm.end is not None
    assert result.ttm.period is not None

    assert result.ttm.start < result.ttm.end, (
        f"{ticker}: invalid TTM dates "
        f"{result.ttm.start} -> {result.ttm.end}"
    )

    assert result.ttm.period.startswith("TTM:"), (
        f"{ticker}: unexpected TTM period label "
        f"{result.ttm.period}"
    )


@pytest.mark.parametrize(
    "ticker,cik",
    list(COMPANIES.items()),
)
def test_multi_company_revenue_scale(ticker, cik):
    result = load_company(ticker, cik)

    if result.ttm is None or result.ttm.revenue is None:
        pytest.fail(f"{ticker}: TTM revenue missing")

    revenue = float(result.ttm.revenue)

    # SEC normalized large-cap revenue should be represented
    # in absolute USD, not USD billions/millions.
    assert revenue >= 1_000_000_000, (
        f"{ticker}: suspicious revenue scale: {revenue}"
    )

    assert revenue < 10_000_000_000_000, (
        f"{ticker}: suspiciously large revenue scale: {revenue}"
    )


@pytest.mark.parametrize(
    "ticker,cik",
    list(COMPANIES.items()),
)
def test_multi_company_financial_scale(ticker, cik):
    result = load_company(ticker, cik)

    ttm = result.ttm

    if ttm is None:
        pytest.fail(f"{ticker}: TTM missing")

    money_fields = [
        "revenue",
        "gross_profit",
        "operating_income",
        "depreciation",
        "amortization",
        "net_income",
        "assets",
        "equity",
        "cash",
        "debt",
        "operating_cash_flow",
        "capex",
        "free_cash_flow",
    ]

    for field in money_fields:
        value = getattr(ttm, field, None)

        if value is None:
            continue

        value = float(value)

        assert abs(value) < 10_000_000_000_000, (
            f"{ticker}: {field} has suspicious absolute scale: {value}"
        )


def test_aapl_ground_truth_remains_locked():
    result = load_company("AAPL", 320193)

    assert result.ttm is not None
    assert result.ttm.revenue == 466_823_000_000.0

    assert result.ttm.period == "TTM:2026-06-27"
    assert result.ttm.start == "2025-06-29"
    assert result.ttm.end == "2026-06-27"


def test_aapl_ttm_formula_remains_locked():
    fy2025 = 416_161_000_000.0
    nine_month_2025 = 313_695_000_000.0
    nine_month_2026 = 364_357_000_000.0

    expected = fy2025 - nine_month_2025 + nine_month_2026

    assert expected == 466_823_000_000.0


def test_ttm_has_required_financial_structure():
    result = load_company("AAPL", 320193)

    assert result.ttm is not None

    required_fields = [
        "period",
        "start",
        "end",
        "revenue",
    ]

    for field in required_fields:
        assert hasattr(result.ttm, field), (
            f"TTM FinancialPeriod missing field: {field}"
        )


def test_normalized_result_has_core_sections():
    result = load_company("AAPL", 320193)

    assert result is not None
    assert hasattr(result, "metrics")
    assert hasattr(result, "periods")
    assert hasattr(result, "quality")
    assert hasattr(result, "ttm")


def test_aapl_revenue_billions_scale():
    result = load_company("AAPL", 320193)

    assert result.ttm is not None

    billions = result.ttm.revenue / 1_000_000_000

    assert billions == 466.823
    assert 100 < billions < 1000

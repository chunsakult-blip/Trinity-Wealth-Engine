import json
from pathlib import Path

from ai.research.financial.normalizer import FinancialFactNormalizer


AAPL_CIK = 320193
AAPL_TICKER = "AAPL"

EXPECTED_FY2025 = 416_161_000_000.0
EXPECTED_9M_FY2025 = 313_695_000_000.0
EXPECTED_9M_FY2026 = 364_357_000_000.0

EXPECTED_TTM_REVENUE = (
    EXPECTED_FY2025
    - EXPECTED_9M_FY2025
    + EXPECTED_9M_FY2026
)


def _load_aapl_companyfacts():
    root = Path(__file__).resolve().parents[2]
    cache = (
        root
        / ".cache"
        / "sec"
        / "companyfacts"
        / "CIK0000320193.json"
    )

    assert cache.exists(), f"AAPL SEC cache missing: {cache}"

    return json.loads(cache.read_text(encoding="utf-8"))


def test_aapl_true_ttm_revenue_ground_truth():
    payload = _load_aapl_companyfacts()

    normalizer = FinancialFactNormalizer()

    result = normalizer.normalize(
        payload,
        cik=AAPL_CIK,
        ticker=AAPL_TICKER,
    )

    assert result.ttm is not None, "TTM period must exist"

    actual = result.ttm.revenue

    assert actual is not None, "TTM revenue must exist"

    assert actual == EXPECTED_TTM_REVENUE, (
        f"AAPL True TTM revenue mismatch: "
        f"expected={EXPECTED_TTM_REVENUE}, actual={actual}"
    )


def test_aapl_true_ttm_revenue_formula():
    expected = (
        EXPECTED_FY2025
        - EXPECTED_9M_FY2025
        + EXPECTED_9M_FY2026
    )

    assert expected == EXPECTED_TTM_REVENUE
    assert expected == 466_823_000_000.0


def test_aapl_true_ttm_period_metadata():
    payload = _load_aapl_companyfacts()

    normalizer = FinancialFactNormalizer()

    result = normalizer.normalize(
        payload,
        cik=AAPL_CIK,
        ticker=AAPL_TICKER,
    )

    assert result.ttm is not None

    assert result.ttm.period == "TTM:2026-06-27"
    assert result.ttm.start == "2025-06-29"
    assert result.ttm.end == "2026-06-27"


def test_aapl_true_ttm_revenue_in_billions():
    payload = _load_aapl_companyfacts()

    normalizer = FinancialFactNormalizer()

    result = normalizer.normalize(
        payload,
        cik=AAPL_CIK,
        ticker=AAPL_TICKER,
    )

    actual_billions = result.ttm.revenue / 1_000_000_000

    assert actual_billions == 466.823

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


def test_aapl_as_of_date_blocks_future_filed_fact():
    import copy

    payload = _load_aapl_companyfacts()
    revenue_node = payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]

    unit_name, entries = next(iter(revenue_node["units"].items()))
    original = entries[0]

    future_fact = copy.deepcopy(original)
    future_fact["val"] = 999_999_999_999_999
    future_fact["filed"] = "2099-01-01"

    entries.append(future_fact)

    normalizer = FinancialFactNormalizer()

    current = normalizer.normalize(
        payload,
        cik=AAPL_CIK,
        ticker=AAPL_TICKER,
    )

    historical = normalizer.normalize(
        payload,
        cik=AAPL_CIK,
        ticker=AAPL_TICKER,
        as_of_date="2026-01-01",
    )

    assert current.ttm is not None
    assert historical.ttm is not None

    assert current.ttm.revenue != historical.ttm.revenue
    assert historical.ttm.revenue < 999_999_999_999_999


def test_aapl_as_of_date_boundary_inclusive():
    payload = _load_aapl_companyfacts()

    normalizer = FinancialFactNormalizer()

    before = normalizer.normalize(
        payload,
        cik=AAPL_CIK,
        ticker=AAPL_TICKER,
        as_of_date="2026-01-29",
    )

    at_filing = normalizer.normalize(
        payload,
        cik=AAPL_CIK,
        ticker=AAPL_TICKER,
        as_of_date="2026-01-30",
    )

    def revenue_evidence_count(result):
        item = next(
            evidence
            for evidence in result.evidence
            if evidence.get("metric") == "revenue"
        )
        return item["count"]

    assert revenue_evidence_count(at_filing) > revenue_evidence_count(before)

def test_financial_engine_passes_as_of_date(monkeypatch):
    from ai.research.financial.engine import FinancialIntelligenceEngine

    captured = {}

    def fake_normalize(payload, **kwargs):
        captured.update(kwargs)

        class FakeFinancials:
            metrics = {}

        return FakeFinancials()

    engine = FinancialIntelligenceEngine()
    monkeypatch.setattr(engine.provider, "fetch", lambda cik: {})
    monkeypatch.setattr(engine.normalizer, "normalize", fake_normalize)
    monkeypatch.setattr(
        engine.metrics,
        "calculate",
        lambda financials: {},
    )
    monkeypatch.setattr(
        engine.quality,
        "evaluate",
        lambda financials: {},
    )

    try:
        engine.analyze_company(
            AAPL_CIK,
            ticker=AAPL_TICKER,
            as_of_date="2026-01-30",
        )
    except Exception:
        pass

    assert captured["as_of_date"] == "2026-01-30"

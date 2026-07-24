"""Unit tests สำหรับ tools/macro/macro_autopsy.py"""
from datetime import datetime, timezone

import pytest

from tools.macro import macro_autopsy
from tools.macro.macro_autopsy import get_typed_macro_autopsy
from schemas.market_data_schemas import MacroObservation


def test_get_typed_macro_autopsy_no_mock_data(monkeypatch):
    macro_autopsy._MACRO_CACHE.clear()

    def fake_yahoo(item):
        return MacroObservation(
            category="other",
            series_id=item["series_id"], label=item["label"], value=100.0,
            unit=item["unit"], observed_at="2026-07-22", provider="Yahoo Finance",
            source_url=f"https://example.test/{item['series_id']}", confidence="high",
        )

    monkeypatch.setattr(macro_autopsy, "_fetch_single_yf_series", fake_yahoo)
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    observations = get_typed_macro_autopsy(investigation_mode="macro")
    assert isinstance(observations, list)

    # ยืนยันว่าไม่มี observation ใดเป็น mock data
    for obs in observations:
        assert isinstance(obs, MacroObservation)
        assert obs.provider != "Mock"
        assert obs.provider != "StaticProxy"
        assert obs.confidence in ("high", "medium")
        assert obs.value is not None
        assert obs.observed_at is not None


def test_force_refresh_bypasses_cached_macro_snapshot(monkeypatch):
    macro_autopsy._MACRO_CACHE.clear()
    calls = []

    def fake_yahoo(item):
        calls.append(item["series_id"])
        return MacroObservation(
            category="other",
            series_id=item["series_id"], label=item["label"], value=float(len(calls)),
            unit=item["unit"], observed_at="2026-07-23", provider="Yahoo Finance",
            source_url=f"https://example.test/{item['series_id']}", confidence="high",
        )

    monkeypatch.setattr(macro_autopsy, "_fetch_single_yf_series", fake_yahoo)
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    cached = get_typed_macro_autopsy(investigation_mode="macro")
    refreshed = get_typed_macro_autopsy(investigation_mode="macro", force_refresh=True)

    assert len(calls) == len(macro_autopsy.STANDARD_MACRO_SERIES) * 2
    assert cached is not refreshed


def test_all_stale_macro_snapshot_is_not_cached(monkeypatch):
    macro_autopsy._MACRO_CACHE.clear()

    def fake_yahoo(item):
        return MacroObservation(
            category="other",
            series_id=item["series_id"], label=item["label"], value=100.0,
            unit=item["unit"], observed_at="2026-07-10", provider="Yahoo Finance",
            source_url=f"https://example.test/{item['series_id']}", is_stale=True, confidence="medium",
        )

    monkeypatch.setattr(macro_autopsy, "_fetch_single_yf_series", fake_yahoo)
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    get_typed_macro_autopsy(investigation_mode="macro")

    assert macro_autopsy._MACRO_CACHE == {}


def test_empty_macro_snapshot_is_not_cached(monkeypatch):
    macro_autopsy._MACRO_CACHE.clear()
    monkeypatch.setattr(macro_autopsy, "_fetch_single_yf_series", lambda _item: None)
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    assert get_typed_macro_autopsy(investigation_mode="macro") == []
    assert macro_autopsy._MACRO_CACHE == {}


def test_monthly_fred_freshness_uses_provider_update_not_observation_period():
    """AG-20: May Core PCE was still current on 2026-07-23."""
    is_stale, reason = macro_autopsy._fred_freshness(
        observed_at="2026-05-01",
        provider_updated_at="2026-06-25T12:43:00+00:00",
        frequency="Monthly",
        now=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )

    assert is_stale is False
    assert "provider update" in reason


def test_monthly_fred_freshness_expires_when_provider_misses_next_cycle():
    is_stale, reason = macro_autopsy._fred_freshness(
        observed_at="2026-05-01",
        provider_updated_at="2026-06-01T12:00:00+00:00",
        frequency="Monthly",
        now=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )

    assert is_stale is True
    assert "provider update" in reason


def test_provider_collection_uses_separate_executor_per_provider(monkeypatch):
    """A slow Yahoo batch must not occupy the executor used by FRED."""
    macro_autopsy._MACRO_CACHE.clear()
    labels = []

    def fake_collect(items, fetcher, *, provider_name):
        labels.append(provider_name)
        item = items[0]
        return [
            MacroObservation(
                category="other",
                series_id=item["series_id"],
                label=item["label"],
                value=100.0,
                unit=item["unit"],
                observed_at="2026-07-23",
                provider=provider_name,
            )
        ]

    monkeypatch.setattr(macro_autopsy, "_collect_provider_observations", fake_collect)
    monkeypatch.setenv("FRED_API_KEY", "test-key")

    observations = get_typed_macro_autopsy(investigation_mode="macro", force_refresh=True)

    assert labels == ["Yahoo Finance", "FRED"]
    assert {item.provider for item in observations} == {"Yahoo Finance", "FRED"}


def test_fred_fetch_carries_release_metadata_into_observation(monkeypatch):
    values = [
        {"date": f"2025-{month:02d}-01", "value": str(100 + month)}
        for month in range(1, 13)
    ]
    values = [
        {"date": "2026-05-01", "value": "130"},
        {"date": "2026-04-01", "value": "129"},
        *reversed(values),
    ]

    def fake_get_json(endpoint, *, api_key, params):
        assert api_key == "key"
        if endpoint == "series":
            return {
                "seriess": [{
                    "frequency": "Monthly",
                    "last_updated": "2026-06-25 07:43:00-05",
                }]
            }
        return {"observations": values}

    captured = {}

    def fake_freshness(**kwargs):
        captured.update(kwargs)
        return False, "provider update is current"

    monkeypatch.setattr(macro_autopsy, "_fred_get_json", fake_get_json)
    monkeypatch.setattr(macro_autopsy, "_fred_freshness", fake_freshness)

    result = macro_autopsy._fetch_single_fred_series(
        {
            "series_id": "PCEPILFE",
            "label": "Core PCE",
            "unit": "% YoY",
            "category": "inflation",
        },
        "key",
    )

    assert result is not None
    assert result.observed_at == "2026-05-01"
    assert result.frequency == "Monthly"
    assert result.provider_updated_at == "2026-06-25 07:43:00-05"
    assert result.is_stale is False
    assert captured == {
        "observed_at": "2026-05-01",
        "provider_updated_at": "2026-06-25 07:43:00-05",
        "frequency": "Monthly",
    }


def test_fred_request_error_never_exposes_api_key(monkeypatch):
    def fail_request(*args, **kwargs):
        raise macro_autopsy.requests.exceptions.ProxyError(
            "failed https://api.test?api_key=super-secret"
        )

    monkeypatch.setattr(macro_autopsy.requests, "get", fail_request)

    with pytest.raises(ValueError) as exc_info:
        macro_autopsy._fred_get_json("series", api_key="super-secret", params={"series_id": "X"})

    assert "super-secret" not in str(exc_info.value)
    assert "ProxyError" in str(exc_info.value)


def test_required_series_recovery_uses_chart_for_batch_misses(monkeypatch):
    brent = MacroObservation(
        category="energy",
        series_id="BZ=F",
        label="Brent",
        value=89.0,
        unit="USD/bbl",
        observed_at="2026-07-23",
        provider="Yahoo Finance (batch recovery)",
    )
    wti = MacroObservation(
        category="energy",
        series_id="CL=F",
        label="WTI",
        value=86.0,
        unit="USD/bbl",
        observed_at="2026-07-23",
        provider="Yahoo Finance (chart recovery)",
    )
    chart_calls = []

    monkeypatch.setattr(
        macro_autopsy,
        "_fetch_yf_batch_series",
        lambda _items: [brent],
    )

    def fake_chart(item):
        chart_calls.append(item["series_id"])
        return wti

    monkeypatch.setattr(macro_autopsy, "_fetch_yahoo_chart_series", fake_chart)

    recovered = macro_autopsy.recover_required_macro_series({"BZ=F", "CL=F"})

    assert [observation.series_id for observation in recovered] == ["BZ=F", "CL=F"]
    assert chart_calls == ["CL=F"]


def test_yahoo_chart_recovery_builds_current_observation(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "chart": {
                    "result": [{
                        "timestamp": [
                            int(datetime(2026, 7, 22, tzinfo=timezone.utc).timestamp()),
                            int(datetime(2026, 7, 23, tzinfo=timezone.utc).timestamp()),
                        ],
                        "indicators": {
                            "quote": [{"close": [84.0, 85.5]}],
                        },
                    }],
                    "error": None,
                }
            }

    monkeypatch.setattr(macro_autopsy.requests, "get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(macro_autopsy, "_business_days_between", lambda _start, _end: 0)

    observation = macro_autopsy._fetch_yahoo_chart_series({
        "series_id": "CL=F",
        "label": "WTI",
        "unit": "USD/bbl",
        "category": "energy",
    })

    assert observation is not None
    assert observation.series_id == "CL=F"
    assert observation.value == 85.5
    assert observation.observed_at == "2026-07-23"
    assert observation.provider == "Yahoo Finance (chart recovery)"
    assert observation.is_stale is False

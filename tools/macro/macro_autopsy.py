"""Typed Macro Autopsy Module — Real-time Quantitative Market & Economic Series

ดึงข้อมูลเศรษฐกิจและตลาดมหภาคแบบ Real-time โดยตรงจาก yfinance และ FRED API
ห้ามใช้ static/mock proxy data เด็ดขาด หาก provider ล้มเหลวต้องระบุสถานะ unavailable อย่างโปร่งใส
"""
from datetime import datetime, timedelta, timezone
from functools import partial
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import quote
from pydantic import BaseModel, Field
import requests
import yfinance as yf

from core.logger import get_logger
from core.providers import ProviderConfig, with_provider_retry

logger = get_logger(__name__)

_MACRO_CACHE: Dict[str, tuple[List["MacroObservation"], float]] = {}
_MACRO_CACHE_TTL_SECONDS = 300.0
_MACRO_PROVIDER_DEADLINE_SECONDS = 10.0
_PROVIDER_REQUEST_TIMEOUT_SECONDS = 8.0
_MACRO_PROVIDER_MAX_WORKERS = 10
_FRED_API_BASE = "https://api.stlouisfed.org/fred"


def _business_days_between(start: datetime, end: datetime) -> int:
    """Count completed weekday gaps for market data freshness.

    A Friday close is not stale on the following Monday merely because three
    calendar dates have passed.  FRED release cadence is handled separately.
    """
    if end.date() <= start.date():
        return 0
    current = start.date()
    count = 0
    while current < end.date():
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return count


from schemas.market_data_schemas import MacroObservation


STANDARD_MACRO_SERIES = [
    {"series_id": "BZ=F", "label": "ราคาน้ำมันดิบ Brent", "unit": "USD/bbl", "category": "energy"},
    {"series_id": "CL=F", "label": "ราคาน้ำมันดิบ WTI", "unit": "USD/bbl", "category": "energy"},
    {"series_id": "^GSPC", "label": "ดัชนี S&P 500", "unit": "Points", "category": "equity"},
    {"series_id": "^IXIC", "label": "ดัชนี Nasdaq Composite", "unit": "Points", "category": "equity"},
    {"series_id": "XLE", "label": "Energy Sector ETF (XLE)", "unit": "USD", "category": "sector"},
    {"series_id": "XLK", "label": "Technology Sector ETF (XLK)", "unit": "USD", "category": "sector"},
    {"series_id": "SOXX", "label": "Semiconductor Sector ETF (SOXX)", "unit": "USD", "category": "sector"},
    {"series_id": "GC=F", "label": "ราคาทองคำ Gold Futures", "unit": "USD/oz", "category": "commodity"},
    {"series_id": "DX-Y.NYB", "label": "ดัชนีเงินดอลลาร์ DXY", "unit": "Index", "category": "fx"},
]

FRED_SERIES = [
    {"series_id": "PCEPILFE", "label": "US Core PCE inflation (YoY)", "unit": "% YoY", "category": "inflation", "transform": "yoy"},
    {"series_id": "DGS10", "label": "อัตราผลตอบแทนพันธบัตรรัฐบาลสหรัฐฯ 10 ปี", "unit": "%", "category": "rates"},
    {"series_id": "DGS2", "label": "อัตราผลตอบแทนพันธบัตรรัฐบาลสหรัฐฯ 2 ปี", "unit": "%", "category": "rates"},
    {"series_id": "CPIAUCSL", "label": "ดัชนีเงินเฟ้อ CPI สหรัฐฯ", "unit": "Index", "category": "inflation"},
    {"series_id": "PCEPI", "label": "ดัชนีเงินเฟ้อ PCE", "unit": "Index", "category": "inflation"},
    {"series_id": "T5YIE", "label": "5-Year Breakeven Inflation Rate", "unit": "%", "category": "inflation"},
    {"series_id": "T10YIE", "label": "10-Year Breakeven Inflation Rate", "unit": "%", "category": "inflation"},
]


def _build_yahoo_observation(
    item: Dict[str, str],
    observed_dates: List[Any],
    close_values: List[Any],
    *,
    provider: str = "Yahoo Finance",
) -> Optional[MacroObservation]:
    """Normalize history from either yfinance or Yahoo's chart endpoint."""
    valid_points: List[tuple[Any, float]] = []
    for observed_date, close_value in zip(observed_dates, close_values):
        try:
            numeric_value = float(close_value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric_value):
            valid_points.append((observed_date, numeric_value))
    if len(valid_points) < 2:
        return None

    dates = [point[0] for point in valid_points]
    closes = [point[1] for point in valid_points]
    latest_close = closes[-1]
    prev_close = closes[-2]
    if prev_close == 0:
        return None

    raw_last_dt = dates[-1]
    if hasattr(raw_last_dt, "to_pydatetime"):
        raw_last_dt = raw_last_dt.to_pydatetime()
    if isinstance(raw_last_dt, datetime):
        last_dt = raw_last_dt
    else:
        last_dt = datetime.fromisoformat(str(raw_last_dt))
    if last_dt.tzinfo is not None:
        last_dt = last_dt.astimezone(timezone.utc).replace(tzinfo=None)

    def _return_from_offset(offset: int) -> Optional[float]:
        base_value = closes[-min(offset, len(closes))]
        if base_value == 0:
            return None
        return ((latest_close - base_value) / base_value) * 100.0

    change_pct = ((latest_close - prev_close) / prev_close) * 100.0
    business_day_gap = _business_days_between(last_dt, datetime.now())
    obs_date = last_dt.strftime("%Y-%m-%d")
    return MacroObservation(
        series_id=item["series_id"],
        category=item.get("category", "other"),
        label=item["label"],
        value=round(latest_close, 2),
        unit=item["unit"],
        observed_at=obs_date,
        provider=provider,
        source_url=f"https://finance.yahoo.com/quote/{item['series_id']}",
        previous_value=round(prev_close, 2),
        change_pct=round(change_pct, 2),
        returns={
            "1D": round(change_pct, 2),
            "5D": round(value, 2) if (value := _return_from_offset(6)) is not None else None,
            "30D": round(value, 2) if (value := _return_from_offset(22)) is not None else None,
            "90D": round(value, 2) if (value := _return_from_offset(65)) is not None else None,
        },
        is_stale=business_day_gap > 3,
        confidence="high" if business_day_gap <= 3 else "medium",
        frequency="Daily",
        provider_updated_at=obs_date,
        freshness_reason=f"{business_day_gap} completed business-day gap (maximum 3)",
    )


@with_provider_retry("Yahoo Finance", max_retries=3, timeout_seconds=_PROVIDER_REQUEST_TIMEOUT_SECONDS)
def _get_yf_history(sid: str) -> Any:
    ticker = yf.Ticker(sid)
    return ticker.history(period="6mo", timeout=_PROVIDER_REQUEST_TIMEOUT_SECONDS)

def _fetch_single_yf_series(item: Dict[str, str]) -> Optional[MacroObservation]:
    sid = item["series_id"]
    try:
        hist = _get_yf_history(sid)
        if hist is None or hist.empty or len(hist) < 2 or "Close" not in hist:
            return None

        return _build_yahoo_observation(
            item,
            list(hist.index),
            list(hist["Close"]),
        )
    except Exception as e:
        logger.warning("Failed fetching Yahoo Finance series %s: %s", sid, e)
        return None


def _fetch_yf_batch_series(items: List[Dict[str, str]]) -> List[MacroObservation]:
    """Use yfinance's batch path as an independent fallback for missing tickers."""
    if not items:
        return []
    series_ids = [item["series_id"] for item in items]
    try:
        downloaded = yf.download(
            tickers=series_ids,
            period="6mo",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=False,
            progress=False,
            timeout=_PROVIDER_REQUEST_TIMEOUT_SECONDS,
            multi_level_index=True,
        )
    except Exception as exc:
        logger.warning(
            "Yahoo Finance targeted batch failed for %s (%s)",
            series_ids,
            exc.__class__.__name__,
        )
        return []
    if downloaded is None or downloaded.empty:
        return []

    observations: List[MacroObservation] = []
    columns = downloaded.columns
    for item in items:
        sid = item["series_id"]
        history = None
        try:
            if getattr(columns, "nlevels", 1) == 1:
                if len(items) == 1 and "Close" in columns:
                    history = downloaded
            elif sid in set(columns.get_level_values(0)):
                history = downloaded[sid]
            elif sid in set(columns.get_level_values(1)):
                history = downloaded.xs(sid, axis=1, level=1)
            if history is None or "Close" not in history:
                continue
            observation = _build_yahoo_observation(
                item,
                list(history.index),
                list(history["Close"]),
                provider="Yahoo Finance (batch recovery)",
            )
            if observation:
                observations.append(observation)
        except Exception as exc:
            logger.warning(
                "Yahoo Finance targeted batch could not parse %s (%s)",
                sid,
                exc.__class__.__name__,
            )
    return observations


def _fetch_yahoo_chart_series(item: Dict[str, str]) -> Optional[MacroObservation]:
    """Fetch one missing ticker without sharing yfinance's cookie/session state."""
    sid = item["series_id"]
    try:
        response = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(sid, safe='')}",
            params={"range": "6mo", "interval": "1d", "events": "history"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; InvestAgents/1.0)"},
            timeout=_PROVIDER_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        chart = payload.get("chart") or {}
        if chart.get("error"):
            logger.warning("Yahoo chart recovery returned an error for %s", sid)
            return None
        results = chart.get("result") or []
        if not results:
            return None
        result = results[0]
        timestamps = result.get("timestamp") or []
        quote_items = ((result.get("indicators") or {}).get("quote") or [])
        closes = quote_items[0].get("close") if quote_items else []
        observed_dates = [
            datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
            for timestamp in timestamps
        ]
        return _build_yahoo_observation(
            item,
            observed_dates,
            list(closes or []),
            provider="Yahoo Finance (chart recovery)",
        )
    except Exception as exc:
        logger.warning(
            "Yahoo chart recovery failed for %s (%s)",
            sid,
            exc.__class__.__name__,
        )
        return None


def recover_required_macro_series(series_ids: set[str]) -> List[MacroObservation]:
    """Recover only series required by a briefing preflight.

    This avoids rerunning the entire Yahoo basket when FRED and unrelated
    market observations are already current.  It also uses two independent
    request paths so a poisoned yfinance session is not a terminal failure.
    """
    requested = {str(series_id).upper() for series_id in series_ids}
    item_by_id = {
        str(item["series_id"]).upper(): item
        for item in STANDARD_MACRO_SERIES
        if str(item["series_id"]).upper() in requested
    }
    items = list(item_by_id.values())
    if not items:
        logger.warning("No supported Yahoo macro series matched targeted recovery request: %s", sorted(requested))
        return []

    recovered_by_id = {
        observation.series_id.upper(): observation
        for observation in _fetch_yf_batch_series(items)
        if not observation.is_stale
    }
    missing_items = [
        item
        for series_id, item in item_by_id.items()
        if series_id not in recovered_by_id
    ]
    if missing_items:
        chart_observations = _collect_provider_observations(
            missing_items,
            _fetch_yahoo_chart_series,
            provider_name="Yahoo Finance chart recovery",
        )
        for observation in chart_observations:
            if not observation.is_stale:
                recovered_by_id[observation.series_id.upper()] = observation

    logger.info(
        "Targeted macro recovery requested=%s recovered=%s missing=%s",
        sorted(requested),
        sorted(recovered_by_id),
        sorted(requested - set(recovered_by_id)),
    )
    return sorted(recovered_by_id.values(), key=lambda observation: observation.series_id)


def _parse_provider_datetime(value: Any) -> Optional[datetime]:
    clean = str(value or "").strip()
    if not clean:
        return None
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    # FRED may return an hour-only UTC offset (for example ``-05``).
    if len(clean) >= 3 and clean[-3] in {"+", "-"} and clean[-2:].isdigit():
        clean += ":00"
    try:
        parsed = datetime.fromisoformat(clean)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fred_freshness(
    *,
    observed_at: str,
    provider_updated_at: Optional[str],
    frequency: Optional[str],
    now: Optional[datetime] = None,
) -> tuple[bool, str]:
    """Use a FRED release/update timestamp instead of its period label.

    A monthly observation dated May 1 can be published in late June and remain
    the current official value until late July.  Treating May 1 as its release
    timestamp was the false-stale root cause in AG-20.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    frequency_clean = str(frequency or "").strip().casefold()
    cutoffs = {
        "daily": 7,
        "weekly": 14,
        "biweekly": 21,
        "monthly": 45,
        "quarterly": 120,
        "annual": 400,
    }
    cutoff = next((days for name, days in cutoffs.items() if name in frequency_clean), 45)
    updated = _parse_provider_datetime(provider_updated_at)
    if updated is not None:
        age_days = max(0, (current - updated).days)
        return (
            age_days > cutoff,
            f"provider update age {age_days} days (maximum {cutoff} for {frequency or 'unknown frequency'})",
        )

    # A metadata outage must not silently revert to treating a monthly
    # first-of-month period label like a daily market close.
    observed = _parse_provider_datetime(observed_at)
    if observed is None:
        return True, "missing provider update and unparseable observation period"
    fallback_cutoffs = {
        "daily": 10,
        "weekly": 21,
        "biweekly": 35,
        "monthly": 100,
        "quarterly": 220,
        "annual": 500,
    }
    fallback_cutoff = next(
        (days for name, days in fallback_cutoffs.items() if name in frequency_clean),
        100,
    )
    age_days = max(0, (current - observed).days)
    return (
        age_days > fallback_cutoff,
        f"observation-period fallback age {age_days} days (maximum {fallback_cutoff}); provider update unavailable",
    )


@with_provider_retry("FRED API", max_retries=3, timeout_seconds=_PROVIDER_REQUEST_TIMEOUT_SECONDS)
def _fred_get_json(endpoint: str, *, api_key: str, params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = requests.get(
            f"{_FRED_API_BASE}/{endpoint}",
            params={**params, "api_key": api_key, "file_type": "json"},
            timeout=_PROVIDER_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        # Requests exceptions include the fully prepared URL.  FRED API keys
        # are query parameters, so never propagate that URL into job logs.
        raise ConnectionError(
            f"FRED {endpoint} request failed ({exc.__class__.__name__})"
        ) from exc
    except ValueError as exc:
        raise ValueError(f"FRED {endpoint} returned invalid JSON") from exc
    if isinstance(payload, dict) and payload.get("error_message"):
        raise ValueError(str(payload["error_message"]))
    return payload


def _fetch_single_fred_series(item: Dict[str, str], api_key: str) -> Optional[MacroObservation]:
    sid = item["series_id"]
    try:
        observations_payload = _fred_get_json(
            "series/observations",
            api_key=api_key,
            params={
                "series_id": sid,
                "limit": 24,
                "sort_order": "desc",
            },
        )
        metadata_payload = _fred_get_json(
            "series",
            api_key=api_key,
            params={"series_id": sid},
        )
        values: List[tuple[str, float]] = []
        for observation in observations_payload.get("observations") or []:
            try:
                values.append((str(observation["date"]), float(observation["value"])))
            except (KeyError, TypeError, ValueError):
                continue
        if not values:
            return None

        latest_val = values[0][1]
        prev_val = values[1][1] if len(values) >= 2 else latest_val
        obs_date = values[0][0]
        metadata_items = metadata_payload.get("seriess") or []
        metadata = metadata_items[0] if metadata_items else {}
        frequency = str(metadata.get("frequency") or item.get("frequency") or "")
        provider_updated_at = str(metadata.get("last_updated") or "") or None

        # CPI/PCE are levels.  Their decision-useful comparison is inflation
        # versus the equivalent release a year ago, not a fictitious daily move.
        is_yoy_series = sid in {"CPIAUCSL", "PCEPI", "PCEPILFE"}
        if is_yoy_series and len(values) >= 13:
            year_ago = values[12][1]
            prior_year_ago = values[13][1] if len(values) >= 14 else year_ago
            latest_val = ((latest_val - year_ago) / year_ago) * 100.0 if year_ago else 0.0
            prev_val = ((prev_val - prior_year_ago) / prior_year_ago) * 100.0 if prior_year_ago else latest_val
            unit = "% YoY"
            returns: Dict[str, Optional[float]] = {"release_change": round(latest_val - prev_val, 2)}
        else:
            unit = item["unit"]
            returns = {"period_change": round(((latest_val - prev_val) / prev_val) * 100.0, 2) if prev_val else None}

        chg = float(latest_val - prev_val) if is_yoy_series else float(((latest_val - prev_val) / prev_val) * 100.0) if prev_val else 0.0
        is_stale, freshness_reason = _fred_freshness(
            observed_at=obs_date,
            provider_updated_at=provider_updated_at,
            frequency=frequency,
        )

        return MacroObservation(
            series_id=sid,
            category=item.get("category", "other"),
            label=item["label"],
            value=round(latest_val, 2),
            unit=unit,
            observed_at=obs_date,
            provider="FRED (Federal Reserve)",
            source_url=f"https://fred.stlouisfed.org/series/{sid}",
            previous_value=round(prev_val, 2),
            change_pct=round(chg, 2),
            returns=returns,
            is_stale=is_stale,
            confidence="high" if not is_stale else "medium",
            frequency=frequency or None,
            provider_updated_at=provider_updated_at,
            freshness_reason=freshness_reason,
        )
    except Exception as e:
        logger.warning("Failed fetching FRED series %s: %s", sid, e)
        return None


def _collect_provider_observations(
    items: List[Dict[str, str]],
    fetcher: Any,
    *,
    provider_name: str,
) -> List[MacroObservation]:
    """Collect a provider without sharing a worker queue with other providers."""
    if not items:
        return []
    executor = ThreadPoolExecutor(
        max_workers=min(len(items), _MACRO_PROVIDER_MAX_WORKERS),
        thread_name_prefix=f"macro_{provider_name.casefold().replace(' ', '_')}",
    )
    future_to_item = {executor.submit(fetcher, item): item for item in items}
    done, pending = wait(future_to_item, timeout=_MACRO_PROVIDER_DEADLINE_SECONDS)
    for future in pending:
        future.cancel()
    if pending:
        logger.warning(
            "%s macro provider deadline exceeded; incomplete series=%s",
            provider_name,
            [future_to_item[future]["series_id"] for future in pending],
        )
    observations: List[MacroObservation] = []
    for future in done:
        try:
            observation = future.result()
        except Exception as exc:
            logger.warning("%s macro provider worker failed: %s", provider_name, exc)
            continue
        if observation:
            observations.append(observation)
    # Network calls have per-request timeouts.  Avoid waiting again here and,
    # crucially, do not put a forced refresh behind the old provider queue.
    executor.shutdown(wait=False, cancel_futures=True)
    return observations


def get_typed_macro_autopsy(
    investigation_mode: str = "macro",
    keywords: Optional[List[str]] = None,
    *,
    force_refresh: bool = False,
) -> List[MacroObservation]:
    """ดึงชุดข้อมูลมหภาคเชิงปริมาณแบบ Typed Real-time (ห้ามใช้ Mock Data).

    ``force_refresh`` is reserved for a quality-gate recovery attempt.  It
    bypasses a process-local cache so a transient stale provider response does
    not make a newly approved Briefing Book fail without one fresh read.
    """
    keyword_key = ",".join(sorted(str(k).lower() for k in (keywords or [])))
    cache_key = f"{investigation_mode}:{keyword_key}:{bool(os.getenv('FRED_API_KEY'))}"
    now = time.monotonic()
    cached = _MACRO_CACHE.get(cache_key)
    if cached and not force_refresh and now - cached[1] < _MACRO_CACHE_TTL_SECONDS:
        return cached[0]
    if force_refresh:
        logger.info("Bypassing macro autopsy cache for a forced freshness refresh (%s)", cache_key)

    observations = _collect_provider_observations(
        STANDARD_MACRO_SERIES,
        _fetch_single_yf_series,
        provider_name="Yahoo Finance",
    )

    # 2. Fetch FRED Series if API Key is configured
    fred_key = ProviderConfig.get_fred_api_key()
    if fred_key:
        observations.extend(
            _collect_provider_observations(
                FRED_SERIES,
                partial(_fetch_single_fred_series, api_key=fred_key),
                provider_name="FRED",
            )
        )
    else:
        logger.info("FRED_API_KEY missing — skipping FRED macro series (returning only verified Yahoo Finance series)")

    observations.sort(key=lambda observation: observation.series_id)

    # Do not retain an all-stale snapshot for five minutes.  It is useful as a
    # diagnostic for the current attempt, but a later job should fetch the
    # provider again instead of inheriting the same terminal quality failure.
    all_stale = bool(observations) and all(observation.is_stale for observation in observations)
    if not observations:
        _MACRO_CACHE.pop(cache_key, None)
        logger.warning("Macro autopsy returned no observations; empty result will not be cached (%s)", cache_key)
    elif all_stale:
        _MACRO_CACHE.pop(cache_key, None)
        logger.warning("Macro autopsy returned only stale observations; result will not be cached (%s)", cache_key)
    else:
        _MACRO_CACHE[cache_key] = (observations, now)
    return observations

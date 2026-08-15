"""Helper for fetching asset calendar data (Earnings Date, Ex-Dividend Date) from Yahoo Finance.

Uses curl_cffi Chrome impersonation session to bypass YFRateLimitError, wrapped with core.retry.with_retry,
and provides in-memory success (4 hrs) & failure (60 secs) caching.
"""
import threading
import time
from typing import Dict, Tuple
import yfinance as yf
from core.retry import with_retry as _with_retry

# yfinance ใช้ crumb/session แบบ global ต่อ process ที่ไม่ thread-safe — ยิง .calendar
# พร้อมกันมากกว่า 1 ตัว (แม้ ticker จะถูกต้องทั้งคู่) มีโอกาส race กันจน Yahoo ตอบ
# "Invalid Crumb" (401) กลับมาแบบเงียบๆ (yfinance กลืน error เองแล้วคืน {} แทนที่จะ raise)
# ต้อง serialize การยิง request จริงเพื่อกัน race นี้
_FETCH_LOCK = threading.Lock()

_CALENDAR_CACHE: Dict[str, Tuple[dict, float]] = {}
_CACHE_TTL_SECONDS = 4 * 3600  # 4 hours

_CALENDAR_FAILED_CACHE: Dict[str, float] = {}
_FAILED_CACHE_TTL_SECONDS = 60.0  # 60 seconds

# ผลลัพธ์ว่างเปล่า (ไม่มีทั้ง Earnings Date และ Ex-Dividend Date) อาจเป็น transient hiccup
# (เช่น yfinance session/crumb เสียเงียบๆ ไม่ raise exception) ไม่ใช่ "ไม่มีกิจกรรมจริง" เสมอไป
# — ใช้ TTL สั้นแบบเดียวกับ failure cache แทนการเชื่อว่าว่างเปล่า = สำเร็จระยะยาว
_EMPTY_RESULT_TTL_SECONDS = _FAILED_CACHE_TTL_SECONDS


def _is_empty_calendar(cal: dict) -> bool:
    return not cal.get("Earnings Date") and not cal.get("Ex-Dividend Date")


def _fetch_yf_calendar_blocking(provider_symbol: str, timeout: float = 5.0) -> dict:
    """Fetch calendar dict with curl_cffi to bypass YFRateLimitError"""
    session = None
    try:
        from curl_cffi import requests as c_requests
        session = c_requests.Session(timeout=timeout, impersonate="chrome")
    except Exception:
        pass

    def _call():
        t = yf.Ticker(provider_symbol, session=session)
        cal = t.calendar
        return cal if isinstance(cal, dict) else {}

    with _FETCH_LOCK:
        return _with_retry(_call)


def get_asset_calendar(provider_symbol: str) -> dict:
    """Returns calendar dict, utilizing memory success & failure cache."""
    clean_sym = provider_symbol.strip().upper()
    now = time.time()

    # Check success cache — ผลลัพธ์ว่างเปล่าใช้ TTL สั้นกว่า เผื่อเป็นแค่ transient hiccup
    if clean_sym in _CALENDAR_CACHE:
        cached_res, ts = _CALENDAR_CACHE[clean_sym]
        effective_ttl = _EMPTY_RESULT_TTL_SECONDS if _is_empty_calendar(cached_res) else _CACHE_TTL_SECONDS
        if now - ts < effective_ttl:
            return cached_res

    # Check failure cache — Raise Exception consistently to reflect failure status in route
    if clean_sym in _CALENDAR_FAILED_CACHE:
        if now - _CALENDAR_FAILED_CACHE[clean_sym] < _FAILED_CACHE_TTL_SECONDS:
            raise RuntimeError(f"Calendar fetch previously failed for {clean_sym} (cached)")

    try:
        cal = _fetch_yf_calendar_blocking(clean_sym)
        _CALENDAR_CACHE[clean_sym] = (cal, now)
        return cal
    except Exception as exc:
        _CALENDAR_FAILED_CACHE[clean_sym] = now
        raise exc

"""Unit tests for tools/market/calendar.py in-memory caching behavior.

Phase 2 ของ fix Corporate Calendar bug (2026-08-12): ผลลัพธ์ว่างเปล่า (ไม่มีทั้ง
Earnings Date และ Ex-Dividend Date) ต้อง cache ด้วย TTL สั้น (เหมือน failure cache)
แทน TTL ยาว 4 ชม. เพราะอาจเป็นแค่ transient hiccup (เช่น yfinance session/crumb
เสียเงียบๆ) ไม่ใช่ "ไม่มีกิจกรรมจริง" เสมอไป
"""
import pytest

import tools.market.calendar as calendar_mod


@pytest.fixture(autouse=True)
def _clear_calendar_caches():
    """กัน state รั่วข้าม test — module-level dict ไม่ reset เองระหว่าง test"""
    calendar_mod._CALENDAR_CACHE.clear()
    calendar_mod._CALENDAR_FAILED_CACHE.clear()
    yield
    calendar_mod._CALENDAR_CACHE.clear()
    calendar_mod._CALENDAR_FAILED_CACHE.clear()


def test_empty_result_refetches_after_short_ttl(monkeypatch):
    """ผลลัพธ์ว่างเปล่าต้องหมดอายุเร็ว (60s) ไม่ใช่ 4 ชม. เผื่อเป็นแค่ transient hiccup"""
    call_count = {"n": 0}

    def fake_fetch(symbol, timeout=5.0):
        call_count["n"] += 1
        return {}

    monkeypatch.setattr(calendar_mod, "_fetch_yf_calendar_blocking", fake_fetch)

    fake_now = [1000.0]
    monkeypatch.setattr(calendar_mod.time, "time", lambda: fake_now[0])

    assert calendar_mod.get_asset_calendar("PG") == {}
    assert call_count["n"] == 1

    # ยังไม่ถึง 60 วินาที — ต้องยังใช้ cache เดิม ไม่ fetch ซ้ำ
    fake_now[0] = 1000.0 + 30
    assert calendar_mod.get_asset_calendar("PG") == {}
    assert call_count["n"] == 1

    # เกิน 60 วินาที — ต้อง fetch ใหม่
    fake_now[0] = 1000.0 + 61
    assert calendar_mod.get_asset_calendar("PG") == {}
    assert call_count["n"] == 2


def test_nonempty_result_stays_cached_past_short_ttl(monkeypatch):
    """ผลลัพธ์ที่มีข้อมูลจริงต้องยัง cache นาน 4 ชม. ตามปกติ ไม่ใช่หมดอายุเร็วแบบผลลัพธ์ว่าง"""
    call_count = {"n": 0}
    real_cal = {"Earnings Date": ["2026-10-22"], "Ex-Dividend Date": "2026-07-24"}

    def fake_fetch(symbol, timeout=5.0):
        call_count["n"] += 1
        return real_cal

    monkeypatch.setattr(calendar_mod, "_fetch_yf_calendar_blocking", fake_fetch)

    fake_now = [2000.0]
    monkeypatch.setattr(calendar_mod.time, "time", lambda: fake_now[0])

    assert calendar_mod.get_asset_calendar("PG") == real_cal
    assert call_count["n"] == 1

    # ผ่านไป 61 วินาที (เกิน short TTL แต่ยังไม่เกิน 4 ชม.) — ต้องยังใช้ cache เดิม
    fake_now[0] = 2000.0 + 61
    assert calendar_mod.get_asset_calendar("PG") == real_cal
    assert call_count["n"] == 1

    # เกิน 4 ชม. — ต้อง fetch ใหม่
    fake_now[0] = 2000.0 + 4 * 3600 + 1
    assert calendar_mod.get_asset_calendar("PG") == real_cal
    assert call_count["n"] == 2


def test_is_empty_calendar():
    assert calendar_mod._is_empty_calendar({}) is True
    assert calendar_mod._is_empty_calendar({"Dividend Date": "2026-08-17"}) is True
    assert calendar_mod._is_empty_calendar({"Earnings Date": ["2026-10-22"]}) is False
    assert calendar_mod._is_empty_calendar({"Ex-Dividend Date": "2026-07-24"}) is False

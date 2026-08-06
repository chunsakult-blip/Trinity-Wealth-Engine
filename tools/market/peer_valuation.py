"""Peer/Sector Relative Valuation — เทียบ P/E, EV/EBITDA ของหุ้นกับ basket ของหุ้นตัวแทน sector เดียวกัน

ใช้ sector (จาก yfinance .info) เลือก basket แทนการ hardcode peer ต่อ ticker — scale ได้กว้างกว่า
และบำรุงรักษาง่ายกว่า มิเรอร์ pattern เดียวกับ curated lists ใน tools/market/asset_resolver.py

ไม่รวมใน composite_score — เป็น contextual indicator แยกต่างหาก (ดู schemas/micro_quant_schemas.py)
"""
import time
from typing import Dict, List, Optional, Tuple

from langsmith import traceable

from core.logger import get_logger
from .core import _yf_info
from .quant_scoring import _linear_score

log = get_logger(__name__)

# ครอบคลุมเฉพาะ US large-cap ที่มีสภาพคล่องสูง — TH market ยังไม่มี basket รองรับ (ได้ None/flag
# ตาม pattern เดิมที่ยอมรับว่า TH จะมีข้อมูลไม่ครบเท่า US)
_SECTOR_PEER_BASKETS: Dict[str, List[str]] = {
    "Technology": ["MSFT", "GOOGL", "NVDA", "ORCL"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD"],
    "Communication Services": ["META", "GOOGL", "NFLX", "DIS"],
    "Healthcare": ["UNH", "JNJ", "PFE", "ABBV"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT"],
    "Energy": ["XOM", "CVX", "COP"],
    "Industrials": ["CAT", "HON", "UNP"],
}

_MIN_VALID_PEERS = 2

# TTL cache แยกของไฟล์นี้ (ไม่แชร์กับ equity_quant_tool.py) — peer เดิมถูกเรียกซ้ำบ่อยข้าม ticker
# ที่วิเคราะห์ (เช่น MSFT เป็น peer ของหุ้น Technology แทบทุกตัว) จึง cache ไว้ลดโหลดจริง
_PEER_INFO_CACHE: Dict[str, Tuple[dict, float]] = {}
_PEER_INFO_ERROR_CACHE: Dict[str, float] = {}
_PEER_INFO_SUCCESS_TTL_SECONDS = 6 * 3600
_PEER_INFO_ERROR_TTL_SECONDS = 60.0


def _get_peer_info_cached(symbol: str) -> dict:
    now = time.time()
    if symbol in _PEER_INFO_CACHE:
        info, ts = _PEER_INFO_CACHE[symbol]
        if now - ts < _PEER_INFO_SUCCESS_TTL_SECONDS:
            return info
        del _PEER_INFO_CACHE[symbol]

    if symbol in _PEER_INFO_ERROR_CACHE:
        ts = _PEER_INFO_ERROR_CACHE[symbol]
        if now - ts < _PEER_INFO_ERROR_TTL_SECONDS:
            raise RuntimeError(f"cached failure for peer {symbol}")
        del _PEER_INFO_ERROR_CACHE[symbol]

    try:
        info = _yf_info(symbol)
    except Exception:
        _PEER_INFO_ERROR_CACHE[symbol] = now
        raise

    _PEER_INFO_CACHE[symbol] = (info, now)
    return info


@traceable(run_type="tool")
def fetch_peer_metrics(sector: Optional[str], exclude_ticker: str) -> List[dict]:
    """ดึง trailingPE/enterpriseToEbitda ของ peer ใน sector basket เดียวกัน (ตัด self ออก)

    Returns:
        list[dict]: แต่ละ dict มี {symbol, pe, ev_ebitda} — ข้าม peer ที่ดึงข้อมูลไม่สำเร็จ (ไม่ error ทั้งชุด)
    """
    if not sector:
        return []
    basket = _SECTOR_PEER_BASKETS.get(sector, [])
    peers = [p for p in basket if p.upper() != exclude_ticker.upper()]

    results: List[dict] = []
    for peer_symbol in peers:
        try:
            info = _get_peer_info_cached(peer_symbol)
            results.append({
                "symbol": peer_symbol,
                "pe": info.get("trailingPE"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
            })
        except Exception as e:
            log.warning("fetch_peer_metrics: failed to fetch peer %s: %s", peer_symbol, e)
            continue

    return results


@traceable(run_type="parser")
def compute_peer_relative_score(
    own_pe: Optional[float],
    peer_metrics: List[dict],
) -> Tuple[Optional[float], Optional[float], Optional[int], Optional[str]]:
    """เปรียบเทียบ P/E ของหุ้นกับค่าเฉลี่ย peer ใน sector เดียวกัน

    Threshold: ถูกกว่า peer เฉลี่ย 20% ขึ้นไป → 100, แพงกว่า peer เฉลี่ย 50% ขึ้นไป → 0 (เชิงเส้น)

    Returns:
        (peer_relative_score, pe_vs_peer_avg_pct, peer_count, flag)
    """
    if own_pe is None or own_pe <= 0:
        return None, None, None, "missing_own_pe:peer_relative"

    valid_pes = [p["pe"] for p in peer_metrics if p.get("pe") is not None and p["pe"] > 0]
    if len(valid_pes) < _MIN_VALID_PEERS:
        return None, None, len(valid_pes), "insufficient_peers:peer_relative"

    peer_avg_pe = sum(valid_pes) / len(valid_pes)
    pe_vs_peer_avg_pct = round((own_pe - peer_avg_pe) / peer_avg_pe * 100, 2)

    score = _linear_score(pe_vs_peer_avg_pct, best=-20, worst=50)
    score = round(score, 1) if score is not None else None

    return score, pe_vs_peer_avg_pct, len(valid_pes), None

"""Deterministic price-based Quant Engine — Beta/Volatility/MDD/RSI/MACD คำนวณ local ทั้งหมดจาก yfinance history

ฟังก์ชันในไฟล์นี้เป็น internal helper (ไม่ใช่ @tool) — ถูกเรียกจาก tools/market/equity_quant_tool.py
เท่านั้น เพื่อประกอบ QuantSignals แบบ deterministic ไม่มี LLM แทรกแซงค่าตัวเลข
"""
import time
from datetime import datetime
from typing import Optional, Dict, List, Tuple

import pandas as pd
import yfinance as yf
from langsmith import traceable
from pydantic import BaseModel

from core.logger import get_logger
from core.retry import with_retry as _with_retry
from tools.market.financial_autopsy import FinancialAutopsyPeriod

log = get_logger(__name__)

_MIN_TRADING_DAYS = 45  # เกณฑ์เดียวกับ Correlation Quality Guard ของ Macro (5.7 Pillar 4)


class PriceSeriesQuality(BaseModel):
    trading_days: int
    is_valid: bool
    stale_reason: Optional[str] = None


# --- Shared price-history cache (ลด .history() call ซ้ำระหว่าง beta/vol/mdd/technical ของ ticker เดียวกัน) ---
_HISTORY_CACHE: Dict[Tuple[str, str], Tuple[pd.DataFrame, float]] = {}
_HISTORY_ERROR_CACHE: Dict[Tuple[str, str], float] = {}
_HISTORY_SUCCESS_TTL_SECONDS = 6 * 3600
_HISTORY_ERROR_TTL_SECONDS = 60.0


def _get_price_history(provider_symbol: str, period: str) -> pd.DataFrame:
    """ดึงราคาย้อนหลังพร้อม retry + cache TTL (success 6h / error 60s) ป้องกัน rate-limit จาก .history()"""
    key = (provider_symbol, period)
    now = time.time()

    if key in _HISTORY_CACHE:
        df, ts = _HISTORY_CACHE[key]
        if now - ts < _HISTORY_SUCCESS_TTL_SECONDS:
            return df
        del _HISTORY_CACHE[key]

    if key in _HISTORY_ERROR_CACHE:
        ts = _HISTORY_ERROR_CACHE[key]
        if now - ts < _HISTORY_ERROR_TTL_SECONDS:
            raise RuntimeError(f"cached failure for {provider_symbol} ({period})")
        del _HISTORY_ERROR_CACHE[key]

    try:
        df = _with_retry(lambda: yf.Ticker(provider_symbol).history(period=period))
    except Exception as e:
        log.warning("_get_price_history failed | %s (%s): %s", provider_symbol, period, e)
        _HISTORY_ERROR_CACHE[key] = now
        raise

    _HISTORY_CACHE[key] = (df, now)
    return df


def _quality_from_df(df: Optional[pd.DataFrame]) -> PriceSeriesQuality:
    n = 0 if df is None else len(df)
    if n < _MIN_TRADING_DAYS:
        return PriceSeriesQuality(trading_days=n, is_valid=False, stale_reason="insufficient_trading_history")
    return PriceSeriesQuality(trading_days=n, is_valid=True)


def _fetch_error_quality() -> PriceSeriesQuality:
    return PriceSeriesQuality(trading_days=0, is_valid=False, stale_reason="fetch_error")


@traceable(run_type="tool")
def compute_beta(provider_symbol: str, benchmark: str = "^GSPC", period: str = "2y") -> Tuple[Optional[float], PriceSeriesQuality]:
    """คำนวณ Beta เทียบ benchmark จาก daily returns covariance/variance — ต้องมีวันทำการที่ overlap กันจริง ≥45 วัน"""
    try:
        stock_df = _get_price_history(provider_symbol, period)
        bench_df = _get_price_history(benchmark, period)
    except Exception:
        return None, _fetch_error_quality()

    if stock_df.empty or bench_df.empty or "Close" not in stock_df or "Close" not in bench_df:
        return None, PriceSeriesQuality(trading_days=0, is_valid=False, stale_reason="insufficient_trading_history")

    stock_ret = stock_df["Close"].pct_change().dropna()
    bench_ret = bench_df["Close"].pct_change().dropna()
    aligned = pd.concat([stock_ret, bench_ret], axis=1, join="inner")
    aligned.columns = ["stock", "bench"]
    overlapping_days = len(aligned)

    if overlapping_days < _MIN_TRADING_DAYS:
        return None, PriceSeriesQuality(trading_days=overlapping_days, is_valid=False, stale_reason="insufficient_trading_history")

    variance = aligned["bench"].var()
    if not variance or pd.isna(variance) or variance == 0:
        return None, PriceSeriesQuality(trading_days=overlapping_days, is_valid=False, stale_reason="zero_benchmark_variance")

    covariance = aligned["stock"].cov(aligned["bench"])
    beta = float(covariance / variance)
    return round(beta, 2), PriceSeriesQuality(trading_days=overlapping_days, is_valid=True)


@traceable(run_type="tool")
def compute_volatility(provider_symbol: str, period: str = "1y") -> Tuple[Optional[float], PriceSeriesQuality]:
    """Annualized Volatility (%) จาก std ของ daily returns * sqrt(252)"""
    try:
        df = _get_price_history(provider_symbol, period)
    except Exception:
        return None, _fetch_error_quality()

    quality = _quality_from_df(df)
    if not quality.is_valid or "Close" not in df or df["Close"].empty:
        return None, quality

    returns = df["Close"].pct_change().dropna()
    if returns.empty:
        return None, PriceSeriesQuality(trading_days=quality.trading_days, is_valid=False, stale_reason="insufficient_trading_history")

    vol_pct = float(returns.std() * (252 ** 0.5) * 100)
    return round(vol_pct, 2), quality


@traceable(run_type="tool")
def compute_mdd(provider_symbol: str, period: str = "3y") -> Tuple[Optional[float], PriceSeriesQuality]:
    """Maximum Drawdown (%) จาก running peak-to-trough ของราคาปิด"""
    try:
        df = _get_price_history(provider_symbol, period)
    except Exception:
        return None, _fetch_error_quality()

    quality = _quality_from_df(df)
    if not quality.is_valid or "Close" not in df or df["Close"].empty:
        return None, quality

    close = df["Close"]
    running_max = close.cummax()
    drawdown = (close - running_max) / running_max
    mdd_pct = float(drawdown.min() * 100)
    return round(mdd_pct, 2), quality


@traceable(run_type="tool")
def compute_technical_indicators(provider_symbol: str, period: str = "1y") -> Tuple[Optional[dict], PriceSeriesQuality]:
    """RSI(14) + MACD(12,26,9) จากราคาปิดย้อนหลัง — คืน {rsi_14, macd, macd_signal_line, macd_signal}"""
    try:
        df = _get_price_history(provider_symbol, period)
    except Exception:
        return None, _fetch_error_quality()

    quality = _quality_from_df(df)
    if not quality.is_valid or "Close" not in df or df["Close"].empty:
        return None, quality

    close = df["Close"]

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    # avg_loss==0 ทำให้ rs หารด้วย NaN แล้วได้ NaN ทั้งที่ทางคณิตศาสตร์ RSI ต้องเป็นค่าปลายสุด
    # (ไม่มีวันขาดทุนเลยในช่วง 14 วัน = RSI 100, ราคาทรงตัวไม่ขยับเลย = RSI 50 เป็นกลาง)
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    rsi_14 = float(rsi.iloc[-1]) if not rsi.empty and pd.notna(rsi.iloc[-1]) else None

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_val = float(macd_line.iloc[-1]) if not macd_line.empty and pd.notna(macd_line.iloc[-1]) else None
    signal_val = float(signal_line.iloc[-1]) if not signal_line.empty and pd.notna(signal_line.iloc[-1]) else None

    if rsi_14 is None:
        return None, PriceSeriesQuality(trading_days=quality.trading_days, is_valid=False, stale_reason="insufficient_trading_history")

    macd_signal = None
    if macd_val is not None and signal_val is not None:
        macd_signal = "bullish" if macd_val > signal_val else "bearish"

    return {
        "rsi_14": round(rsi_14, 2),
        "macd": round(macd_val, 4) if macd_val is not None else None,
        "macd_signal_line": round(signal_val, 4) if signal_val is not None else None,
        "macd_signal": macd_signal,
    }, quality


def _fiscal_gap_days(date_a: str, date_b: str) -> Optional[int]:
    """หาจำนวนวันห่างระหว่าง fiscal_period_end 2 ค่า (string 'YYYY-MM-DD') — None ถ้า parse ไม่ได้"""
    try:
        return abs((datetime.fromisoformat(date_a) - datetime.fromisoformat(date_b)).days)
    except (TypeError, ValueError):
        return None


_YOY_GAP_MIN_DAYS = 300
_YOY_GAP_MAX_DAYS = 400


@traceable(run_type="parser")
def compute_growth_rates(periods: List[FinancialAutopsyPeriod]) -> Tuple[dict, List[str]]:
    """คำนวณ Revenue/Net Income YoY Growth จาก periods[0] (ล่าสุด) เทียบ periods[1] (ก่อนหน้า)

    Guard: ต้องมี ≥2 periods และห่างกันจริง 300-400 วัน ไม่งั้นไม่ใช่ 'YoY' ที่แท้จริง (อาจเป็น
    TTM/quarterly ปนมาจาก financial_autopsy's fiscal period clustering) — ไม่คำนวณถ้าไม่ผ่านเกณฑ์
    Guard: ค่า previous ≤ 0 ทำให้ % growth ไม่มีความหมาย (หารด้วยฐานติดลบ/ศูนย์) — ข้ามไป ไม่คำนวณ

    Returns:
        (result_dict, flags) — result_dict มี key revenue_growth_yoy_pct / net_income_growth_yoy_pct
        เป็น None เสมอถ้าคำนวณไม่ได้ ไม่มีการเดา/ประมาณค่าแทน
    """
    result = {"revenue_growth_yoy_pct": None, "net_income_growth_yoy_pct": None}

    if len(periods) < 2:
        return result, ["insufficient_periods:growth"]

    latest, previous = periods[0], periods[1]
    gap_days = _fiscal_gap_days(latest.fiscal_period_end, previous.fiscal_period_end)
    if gap_days is None or not (_YOY_GAP_MIN_DAYS <= gap_days <= _YOY_GAP_MAX_DAYS):
        return result, ["non_annual_period_gap:growth"]

    flags: List[str] = []

    if latest.total_revenue is not None and previous.total_revenue is not None:
        if previous.total_revenue > 0:
            result["revenue_growth_yoy_pct"] = round(
                (latest.total_revenue - previous.total_revenue) / previous.total_revenue * 100, 2
            )
        else:
            flags.append("base_year_negative:revenue_growth")

    if latest.net_income is not None and previous.net_income is not None:
        if previous.net_income > 0:
            result["net_income_growth_yoy_pct"] = round(
                (latest.net_income - previous.net_income) / previous.net_income * 100, 2
            )
        else:
            flags.append("base_year_negative:net_income_growth")

    return result, flags


_PRICE_PERCENTILE_MIN_DAYS = 250  # ~1 ปีเทรดจริง — เกณฑ์ขั้นต่ำให้คำนวณได้แม้ประวัติจะสั้นกว่า 5 ปีเต็ม


@traceable(run_type="tool")
def compute_price_percentile(provider_symbol: str, period: str = "5y") -> Tuple[Optional[float], Optional[float], PriceSeriesQuality]:
    """Percentile rank + Z-score ของราคาปิดล่าสุด เทียบ distribution ราคาปิดย้อนหลัง (period)

    หมายเหตุสำคัญ: นี่คือ Percentile ของ 'ราคา' ไม่ใช่ Valuation Multiple (P/E) — yfinance ไม่มี
    point-in-time fundamentals ให้คำนวณ Valuation Percentile ย้อนหลังได้จริง (ข้อจำกัดเดียวกับที่
    ทำให้ต้องเป็น Forward-tracking แทน Backtest ใน tools/market/quant_history.py)

    Guard: ต้องมี ≥250 trading days ไม่งั้น None + insufficient_trading_history
    """
    try:
        df = _get_price_history(provider_symbol, period)
    except Exception:
        return None, None, _fetch_error_quality()

    trading_days = 0 if df is None else len(df)
    if trading_days < _PRICE_PERCENTILE_MIN_DAYS or df is None or "Close" not in df or df["Close"].empty:
        return None, None, PriceSeriesQuality(trading_days=trading_days, is_valid=False, stale_reason="insufficient_trading_history")

    close = df["Close"]
    current_price = float(close.iloc[-1])
    percentile = float((close <= current_price).mean() * 100)

    std = float(close.std())
    zscore = 0.0 if std == 0 else float((current_price - close.mean()) / std)

    return round(percentile, 2), round(zscore, 2), PriceSeriesQuality(trading_days=trading_days, is_valid=True)

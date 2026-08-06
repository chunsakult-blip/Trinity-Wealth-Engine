"""Typed Asset Resolver สำหรับตรวจสอบและจำแนกประเภทสินทรัพย์ (Stock, ETF, Macro, etc.) ก่อนเข้าถึงข้อมูลพื้นฐาน"""
from enum import Enum
from typing import Optional, Literal, Dict, Tuple, Any
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from threading import BoundedSemaphore
import time
import requests
import yfinance as yf
from pydantic import BaseModel
from core.logger import get_logger

log = get_logger(__name__)

_SHARED_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="yf_resolver_pool")
_POOL_SEMAPHORE = BoundedSemaphore(4)


class ProviderBusyError(Exception):
    """Raised when bounded pool semaphore cannot be acquired within admission deadline."""
    pass


def _run_with_deadline(func, args, timeout_sec: float, admission_timeout: float = 0.5):
    if not _POOL_SEMAPHORE.acquire(timeout=admission_timeout):
        raise ProviderBusyError("PROVIDER_BUSY: Resolver pool saturated")
    def _worker():
        try:
            return func(*args)
        finally:
            _POOL_SEMAPHORE.release()
    future = _SHARED_POOL.submit(_worker)
    try:
        return future.result(timeout=timeout_sec)
    except (FuturesTimeoutError, TimeoutError) as e:
        future.cancel()
        raise FuturesTimeoutError(f"Operation timed out after {timeout_sec}s") from e


_run_with_hard_timeout = _run_with_deadline


class AssetClass(str, Enum):
    STOCK_TH = "STOCK_TH"
    STOCK_US = "STOCK_US"
    ETF = "ETF"
    CRYPTO = "CRYPTO"
    COMMODITY = "COMMODITY"
    INDEX = "INDEX"
    FX = "FX"
    OTHER = "OTHER"


class ResolvedAsset(BaseModel):
    raw_symbol: str
    provider_symbol: Optional[str]
    asset_class: AssetClass
    market: Optional[Literal["TH", "US"]] = None
    confidence: Literal["high", "medium", "low"]
    eligible_for_financial_autopsy: bool


# --- Curated Registries ---
_CURATED_SET_SYMBOLS = {
    "PTT", "PTTEP", "DELTA", "ADVANC", "CPALL", "AOT", "KBANK", "SCB", "BBL",
    "BDMS", "BH", "GULF", "OR", "CRC", "CPN", "MINT", "TRUE", "BEM", "BTS",
    "MTC", "SAWAD", "TISCO", "KTB", "LH", "IVL", "SCC", "SCGP", "HMPRO", "EA",
    "GPSC", "TOP", "BANPU", "TU", "CPF", "OSP", "CBG", "INTUCH", "RATCH",
    "EGCO", "WHA", "AMATA", "MEGA", "KCE", "HANA"
}

_CURATED_US_EQUITIES = {
    "NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "GOOGL", "GOOG", "META", "INTC",
    "AMD", "XOM", "CVX", "NFLX", "PFE", "COST", "PANW", "BRK-B", "BRK.B"
}

_CURATED_ETFS = {
    "QQQ", "SPY", "XLP", "IYH", "ARKK", "VOO", "VTI", "IVV", "TLT", "GLD", "SLV"
}

_CURATED_ALIASES: Dict[str, Tuple[str, AssetClass, Optional[Literal["TH", "US"]]]] = {
    "BRK.B": ("BRK-B", AssetClass.STOCK_US, "US"),
    "GOOG": ("GOOG", AssetClass.STOCK_US, "US"),
    "NDX": ("^NDX", AssetClass.INDEX, None),
    "DJI": ("^DJI", AssetClass.INDEX, None),
    "SPX": ("^GSPC", AssetClass.INDEX, None),
    "^GSPC": ("^GSPC", AssetClass.INDEX, None),
    "DXY": ("DX-Y.NYB", AssetClass.INDEX, None),
    "OIL": ("CL=F", AssetClass.COMMODITY, None),
    "CL=F": ("CL=F", AssetClass.COMMODITY, None),
    "BRENT": ("BZ=F", AssetClass.COMMODITY, None),
    "GOLD": ("GC=F", AssetClass.COMMODITY, None),
    "BTC": ("BTC-USD", AssetClass.CRYPTO, None),
    "BTC-USD": ("BTC-USD", AssetClass.CRYPTO, None),
}

_CURATED_FX = {
    "USD", "THB", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "CNY",
    "USD/THB", "EUR/USD", "GBP/USD", "USD/JPY"
}

_US_EQUITY_EXCHANGES = {"NYQ", "NMS", "NGM", "ASE", "NASDAQ", "NYSE", "AMEX", "BATS", "PCX", "PNK", "OOTC"}

# --- Cache สำหรับ verify_asset_metadata (12 ชม. สำเร็จ, 60 วินาที ไม่สำเร็จ) ---
_VERIFY_CACHE: Dict[str, Tuple[ResolvedAsset, float]] = {}
_CACHE_TTL_SECONDS = 12 * 3600
_VERIFY_FAILED_CACHE: Dict[str, float] = {}
_FAILED_CACHE_TTL_SECONDS = 60.0


def _fetch_yf_info_blocking(symbol: str, timeout: float = 3.0) -> dict:
    session = None
    try:
        from curl_cffi import requests as c_requests
        # impersonate="chrome" จำเป็น — Session เปล่าไม่มี browser TLS fingerprint ทำให้ Yahoo
        # ตรวจจับเป็น bot และคืน YFRateLimitError ทันทีตั้งแต่ request แรก (ไม่เกี่ยวกับจำนวนครั้งที่ยิงจริง)
        session = c_requests.Session(timeout=timeout, impersonate="chrome")
    except Exception:
        pass
    if session is not None:
        return yf.Ticker(symbol, session=session).info
    return yf.Ticker(symbol).info


def verify_asset_metadata(symbol: str) -> Optional[ResolvedAsset]:
    """ตรวจสอบข้อมูล metadata ของสินทรัพย์จาก Yahoo Finance ภายใต้ deadline พร้อม Cache สำเร็จ/ไม่สำเร็จ"""
    clean_sym = symbol.strip().upper()
    now = time.time()

    # check success cache
    if clean_sym in _VERIFY_CACHE:
        cached_res, timestamp = _VERIFY_CACHE[clean_sym]
        if now - timestamp < _CACHE_TTL_SECONDS:
            return cached_res
        else:
            del _VERIFY_CACHE[clean_sym]

    # check failure cache
    if clean_sym in _VERIFY_FAILED_CACHE:
        failed_ts = _VERIFY_FAILED_CACHE[clean_sym]
        if now - failed_ts < _FAILED_CACHE_TTL_SECONDS:
            return None
        else:
            del _VERIFY_FAILED_CACHE[clean_sym]

    try:
        info = _run_with_deadline(_fetch_yf_info_blocking, (clean_sym, 3.0), timeout_sec=3.0, admission_timeout=0.2)
    except ProviderBusyError as e:
        log.debug("verify_asset_metadata busy for %s: %s", clean_sym, e)
        return None
    except (FuturesTimeoutError, TimeoutError) as e:
        log.debug("verify_asset_metadata timeout for %s: %s", clean_sym, e)
        _VERIFY_FAILED_CACHE[clean_sym] = now
        return None
    except Exception as e:
        log.debug("verify_asset_metadata error for %s: %s", clean_sym, e)
        _VERIFY_FAILED_CACHE[clean_sym] = now
        return None

    if not info or not isinstance(info, dict):
        _VERIFY_FAILED_CACHE[clean_sym] = now
        return None

    quote_type = info.get("quoteType")
    if not quote_type:
        _VERIFY_FAILED_CACHE[clean_sym] = now
        return None

    qt = str(quote_type).upper()
    exchange = str(info.get("exchange") or "").upper()

    if qt == "EQUITY":
        if clean_sym.endswith(".BK") or "SET" in exchange or "BK" in exchange or "THAI" in exchange:
            res = ResolvedAsset(
                raw_symbol=symbol,
                provider_symbol=clean_sym if clean_sym.endswith(".BK") else f"{clean_sym}.BK",
                asset_class=AssetClass.STOCK_TH,
                market="TH",
                confidence="medium",
                eligible_for_financial_autopsy=True,
            )
        elif exchange in _US_EQUITY_EXCHANGES:
            res = ResolvedAsset(
                raw_symbol=symbol,
                provider_symbol=clean_sym,
                asset_class=AssetClass.STOCK_US,
                market="US",
                confidence="medium",
                eligible_for_financial_autopsy=True,
            )
        else:
            res = ResolvedAsset(
                raw_symbol=symbol,
                provider_symbol=clean_sym,
                asset_class=AssetClass.OTHER,
                market=None,
                confidence="medium",
                eligible_for_financial_autopsy=False,
            )
    elif qt == "ETF":
        res = ResolvedAsset(
            raw_symbol=symbol,
            provider_symbol=clean_sym,
            asset_class=AssetClass.ETF,
            market="US",
            confidence="medium",
            eligible_for_financial_autopsy=False,
        )
    elif qt == "INDEX":
        res = ResolvedAsset(
            raw_symbol=symbol,
            provider_symbol=clean_sym,
            asset_class=AssetClass.INDEX,
            market=None,
            confidence="medium",
            eligible_for_financial_autopsy=False,
        )
    elif qt == "CRYPTOCURRENCY":
        res = ResolvedAsset(
            raw_symbol=symbol,
            provider_symbol=clean_sym,
            asset_class=AssetClass.CRYPTO,
            market=None,
            confidence="medium",
            eligible_for_financial_autopsy=False,
        )
    elif qt == "CURRENCY":
        res = ResolvedAsset(
            raw_symbol=symbol,
            provider_symbol=clean_sym,
            asset_class=AssetClass.FX,
            market=None,
            confidence="medium",
            eligible_for_financial_autopsy=False,
        )
    elif qt == "FUTURE":
        res = ResolvedAsset(
            raw_symbol=symbol,
            provider_symbol=clean_sym,
            asset_class=AssetClass.COMMODITY,
            market=None,
            confidence="medium",
            eligible_for_financial_autopsy=False,
        )
    else:
        _VERIFY_FAILED_CACHE[clean_sym] = now
        return None

    _VERIFY_CACHE[clean_sym] = (res, now)
    if clean_sym in _VERIFY_FAILED_CACHE:
        del _VERIFY_FAILED_CACHE[clean_sym]
    return res


def infer_market_hint(event: Any) -> Optional[Literal["TH", "US"]]:
    """คำนวณ market_hint (TH/US) จากข้อมูล event หรือ dictionary ข่าว"""
    if not event:
        return None
    if isinstance(event, dict):
        mkt = event.get("market") or event.get("country")
        tags = event.get("primary_tags") or []
        themes = event.get("extracted_themes") or []
        title = event.get("canonical_title") or event.get("title") or ""
        summary = event.get("comprehensive_summary") or event.get("summary") or ""
    else:
        mkt = getattr(event, "market", None) or getattr(event, "country", None)
        tags = getattr(event, "primary_tags", [])
        themes = getattr(event, "extracted_themes", [])
        title = getattr(event, "canonical_title", "") or getattr(event, "title", "")
        summary = getattr(event, "comprehensive_summary", "") or getattr(event, "summary", "")

    if isinstance(mkt, str):
        mkt_up = mkt.strip().upper()
        if mkt_up in ("TH", "THAILAND", "SET"):
            return "TH"
        if mkt_up in ("US", "USA", "UNITED STATES"):
            return "US"

    text_blobs = [str(t).upper() for t in (tags + themes)] + [title.upper(), summary.upper()]
    full_text = " ".join(text_blobs)

    th_keywords = ["THAILAND", "THAI", "SET INDEX", "BANK OF THAILAND", "BOT", "BAHT", "SET50", "SET100", "BKK"]
    us_keywords = ["UNITED STATES", "USA", "NASDAQ", "NYSE", "S&P 500", "FEDERAL RESERVE", "FED", "FOMC", "WALL STREET"]

    for kw in th_keywords:
        if kw in full_text:
            return "TH"
    for kw in us_keywords:
        if kw in full_text:
            return "US"

    return None


def resolve_asset(
    symbol: str,
    market_hint: Optional[Literal["TH", "US"]] = None,
    offline_fallback: bool = False,
) -> ResolvedAsset:
    """จำแนกประเภทและจัดรูปแบบ symbol ก่อนดึงข้อมูล หรือคำนวณโหมดสืบสวน พร้อมใช้ market_hint ก่อน"""
    raw = symbol.strip()
    clean = raw.upper()

    # 1. Check Curated Aliases
    if clean in _CURATED_ALIASES:
        prov_sym, a_class, mkt = _CURATED_ALIASES[clean]
        return ResolvedAsset(
            raw_symbol=raw,
            provider_symbol=prov_sym,
            asset_class=a_class,
            market=mkt,
            confidence="high",
            eligible_for_financial_autopsy=(a_class in (AssetClass.STOCK_TH, AssetClass.STOCK_US)),
        )

    # 2. Check Curated SET Symbols or .BK suffix
    if clean.endswith(".BK") or clean in _CURATED_SET_SYMBOLS:
        prov = clean if clean.endswith(".BK") else f"{clean}.BK"
        return ResolvedAsset(
            raw_symbol=raw,
            provider_symbol=prov,
            asset_class=AssetClass.STOCK_TH,
            market="TH",
            confidence="high",
            eligible_for_financial_autopsy=True,
        )

    # 3. Check Curated US Equities
    if clean in _CURATED_US_EQUITIES:
        prov = "BRK-B" if clean == "BRK.B" else clean
        return ResolvedAsset(
            raw_symbol=raw,
            provider_symbol=prov,
            asset_class=AssetClass.STOCK_US,
            market="US",
            confidence="high",
            eligible_for_financial_autopsy=True,
        )

    # 4. Check Curated ETFs
    if clean in _CURATED_ETFS:
        return ResolvedAsset(
            raw_symbol=raw,
            provider_symbol=clean,
            asset_class=AssetClass.ETF,
            market="US",
            confidence="high",
            eligible_for_financial_autopsy=False,
        )

    # 5. Check Curated FX
    if clean in _CURATED_FX:
        return ResolvedAsset(
            raw_symbol=raw,
            provider_symbol=clean,
            asset_class=AssetClass.FX,
            market=None,
            confidence="high",
            eligible_for_financial_autopsy=False,
        )

    # 6. Verify with Yahoo Finance using market_hint priority (if not offline_fallback)
    if not offline_fallback:
        if market_hint == "TH":
            target_sym = clean if clean.endswith(".BK") else f"{clean}.BK"
            verified = verify_asset_metadata(target_sym)
            if verified is not None:
                return verified
        elif market_hint == "US":
            verified = verify_asset_metadata(clean)
            if verified is not None:
                return verified
        else:
            verified = verify_asset_metadata(clean)
            if verified is not None:
                return verified
            if not clean.endswith(".BK") and len(clean) <= 8 and all(c.isalnum() or c in "-." for c in clean):
                verified_bk = verify_asset_metadata(f"{clean}.BK")
                if verified_bk is not None and verified_bk.asset_class == AssetClass.STOCK_TH:
                    return verified_bk

    # 7. Fallback to OTHER
    return ResolvedAsset(
        raw_symbol=raw,
        provider_symbol=clean,
        asset_class=AssetClass.OTHER,
        market=market_hint,
        confidence="low",
        eligible_for_financial_autopsy=False,
    )


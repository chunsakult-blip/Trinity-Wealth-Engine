"""Smart Money & Ownership Signal Flags Detector — Insider Flow, Short Interest, Institutional Ownership."""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import pandas as pd
import yfinance as yf
from langsmith import traceable
from core.logger import get_logger
from schemas.micro_quant_schemas import SmartMoneyFlags

_INSIDER_WINDOW_DAYS = 90

log = get_logger(__name__)


@traceable(run_type="parser")
def compute_smart_money_flags(ticker: str, info_dict: Optional[dict[str, Any]] = None) -> tuple[SmartMoneyFlags, list[str]]:
    """ประเมินสัญญาณ Smart Money (Insider buying/selling, Short Interest, Institutional Ownership)

    หมายเหตุ: คืนข้อมูลเชิงสัญญาณ (Flag) แยกจากคะแนนตัวเลข ไม่รวมใน Composite Score
    แนบ data_quality_flags '10b51_unfiltered:insider_signal' เสมอเนื่องจาก yfinance ไม่ได้แยก 10b5-1 plans
    """
    flags: list[str] = ["10b51_unfiltered:insider_signal"]

    if info_dict is None:
        try:
            tk = yf.Ticker(ticker)
            info_dict = tk.info or {}
        except Exception as e:
            log.warning("Failed to fetch info for ownership flags (%s): %s", ticker, e)
            info_dict = {}

    inst_pct = info_dict.get("heldPercentInstitutions")
    if inst_pct is not None:
        inst_pct = round(inst_pct * 100.0, 2)

    insider_pct = info_dict.get("heldPercentInsiders")
    if insider_pct is not None:
        insider_pct = round(insider_pct * 100.0, 2)

    short_pct = info_dict.get("shortPercentOfFloat")
    if short_pct is not None:
        short_pct = round(short_pct * 100.0, 2)

    short_squeeze_risk = bool(short_pct is not None and short_pct >= 15.0)

    # Insider transactions (90d)
    insider_buy_count = 0
    insider_sell_count = 0
    insider_signal = "neutral"

    try:
        tk = yf.Ticker(ticker)
        insiders = tk.insider_transactions
        if insiders is not None and not insiders.empty and "Transaction" in insiders.columns:
            date_col = next((c for c in ("Start Date", "Date") if c in insiders.columns), None)
            if date_col is not None:
                cutoff = datetime.now(timezone.utc) - timedelta(days=_INSIDER_WINDOW_DAYS)
                tx_dates = pd.to_datetime(insiders[date_col], errors="coerce", utc=True)
                recent = insiders[tx_dates >= cutoff]
            else:
                # ไม่มีคอลัมน์วันที่ให้กรอง — ไม่สามารถจำกัดช่วง 90 วันได้จริง
                recent = insiders.iloc[0:0]
                flags.append("insider_date_unavailable:insider_signal")

            for _, row in recent.iterrows():
                trans = str(row.get("Transaction", "")).lower()
                if "buy" in trans or "purchase" in trans:
                    insider_buy_count += 1
                elif "sale" in trans or "sell" in trans:
                    insider_sell_count += 1

            if insider_buy_count > insider_sell_count:
                insider_signal = "buying"
            elif insider_sell_count > insider_buy_count:
                insider_signal = "selling"
    except Exception as e:
        log.debug("Could not fetch insider_transactions for %s: %s", ticker, e)

    # Overall Signal Flag
    if insider_signal == "buying" and not short_squeeze_risk:
        overall = "bullish_signal"
    elif insider_signal == "selling" or short_squeeze_risk:
        overall = "bearish_signal"
    else:
        overall = "neutral"

    res = SmartMoneyFlags(
        insider_signal=insider_signal,
        insider_buy_count_90d=insider_buy_count,
        insider_sell_count_90d=insider_sell_count,
        institutional_ownership_pct=inst_pct,
        insider_ownership_pct=insider_pct,
        short_interest_pct=short_pct,
        short_squeeze_risk=short_squeeze_risk,
        overall_smart_money_flag=overall,
    )
    return res, flags

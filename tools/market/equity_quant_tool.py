"""Single @tool ที่รวบรวม Equity Quant Signals ทั้งหมดแบบ deterministic — ผูกกับ equity_quant agent
ตัวเดียว มิเรอร์ evaluate_macro_matrix (tools/macro/evaluation.py) ที่เป็น tool เดียวของ macro_quant

ไม่มี field ตัวเลขไหนใน output มาจากการตัดสินใจของ LLM — LLM ที่ผูกกับ tool นี้มีหน้าที่แค่ตีความ
ticker/market จาก instruction แล้วส่งต่อผลลัพธ์ดิบกลับไปเท่านั้น (ดู prompts/skills/equity_quant/SKILL.md)
"""
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from langchain_core.tools import tool

from core.logger import get_logger
from schemas.micro_quant_schemas import QuantSignals
from tools.market.asset_resolver import resolve_asset
from tools.market.financial_autopsy import get_financial_autopsy
from tools.market.quant_engine import (
    compute_beta,
    compute_volatility,
    compute_mdd,
    compute_technical_indicators,
    compute_growth_rates,
    compute_price_percentile,
)
from tools.market.quant_scoring import (
    compute_value_score,
    compute_quality_score,
    compute_momentum_score,
    compute_price_target_outlook,
    compute_growth_score,
    compute_dividend_score,
    compute_solvency_score,
    compute_trading_liquidity,
    compute_composite_score,
    compute_fcf_quality_score,
    compute_debt_quality_score,
)
from tools.market.peer_valuation import fetch_peer_metrics, compute_peer_relative_score
from tools.market.earnings_momentum import fetch_earnings_revision_data, compute_earnings_revision_score
from tools.macro.evaluation import load_latest_macro_observables
from tools.market.dcf_valuation import compute_dcf_valuation
from tools.market.ownership import compute_smart_money_flags
from .core import _yf_info

log = get_logger(__name__)

# TTL cache local ต่อไฟล์นี้ (ไม่แตะ tools/market/core.py ที่ fundamentals/technical/consensus/news
# ใช้ร่วมกัน เพื่อไม่ให้กระทบ test suite ของไฟล์เหล่านั้น) — ลดการยิง .info ซ้ำเมื่อวิเคราะห์ ticker
# เดิมซ้ำในช่วงเวลาสั้นๆ เช่น re-run วิเคราะห์หุ้นตัวเดิมในหลาย turn ติดกัน
_INFO_CACHE: dict[str, tuple[dict, float]] = {}
_INFO_ERROR_CACHE: dict[str, float] = {}
_INFO_SUCCESS_TTL_SECONDS = 6 * 3600
_INFO_ERROR_TTL_SECONDS = 60.0


def _get_info_cached(provider_symbol: str) -> dict:
    now = time.time()
    if provider_symbol in _INFO_CACHE:
        info, ts = _INFO_CACHE[provider_symbol]
        if now - ts < _INFO_SUCCESS_TTL_SECONDS:
            return info
        del _INFO_CACHE[provider_symbol]

    if provider_symbol in _INFO_ERROR_CACHE:
        ts = _INFO_ERROR_CACHE[provider_symbol]
        if now - ts < _INFO_ERROR_TTL_SECONDS:
            raise RuntimeError(f"cached failure for {provider_symbol}")
        del _INFO_ERROR_CACHE[provider_symbol]

    try:
        info = _yf_info(provider_symbol)
    except Exception:
        _INFO_ERROR_CACHE[provider_symbol] = now
        raise

    _INFO_CACHE[provider_symbol] = (info, now)
    return info


def _ma_cross_label(ma50: Optional[float], ma200: Optional[float]) -> Optional[str]:
    if ma50 is None or ma200 is None:
        return None
    return "golden_cross" if ma50 > ma200 else "death_cross"


@tool
def compute_equity_quant_signals(ticker: str, market: Literal["TH", "US"] = "US") -> str:
    """คำนวณ Quant Signals ของหุ้นรายตัวแบบ deterministic ทั้งหมด — 5 Pillars: Value/Quality/Growth/
    Momentum/Dividend (รวมเป็น Composite Score เดียว) บวก Solvency (Risk Gate แยก) และ Trading Liquidity

    [Usage/When to use]
    ใช้เมื่อต้องการวิเคราะห์เชิงปริมาณของหุ้นรายตัว 1 ตัวแบบสถาบัน — ครอบคลุมการประเมินมูลค่า (Value),
    คุณภาพกิจการ (Quality), การเติบโต (Growth), โมเมนตัมราคา (Momentum), ปันผล (Dividend),
    ความแข็งแรงทางการเงิน (Solvency), สภาพคล่องการซื้อขาย (Trading Liquidity), ความผันผวน
    (Beta/Volatility/MDD) และเป้าหมายราคานักวิเคราะห์ (Upside/Downside) — ทุกค่าคำนวณจาก Python
    ล้วนๆ ไม่มีการประเมินเชิงอัตวิสัย

    [Caution]
    - ค่าที่เป็น None หมายถึงข้อมูลไม่พอ/ไม่มีจริงจาก Yahoo Finance (พบบ่อยกับหุ้นไทยที่ไม่มี
      analyst target price) หรือหุ้นเพิ่ง IPO ที่มีราคาย้อนหลังไม่ถึง 45 วันทำการ — ห้ามเดาแทนค่า None
    - momentum_score วัด 'ความแรงของโมเมนตัมขาขึ้นเชิงเทคนิค' (momentum-chasing) ไม่ใช่คำแนะนำซื้อ
    - dividend_score สูงอาจเป็น 'Value Trap' (ราคาร่วงหนักทำให้ yield ดูสูงลวงตา) ต้องดู payout_ratio ประกอบ
    - solvency_score เป็น Risk Gate แยก ไม่ถูกรวมใน composite_score — ต้องพิจารณาเป็นตัวชี้วัดความเสี่ยง
      leverage แยกต่างหากเสมอ ไม่ใช่ตัวชี้วัดผลตอบแทน
    - adtv_local_currency เป็นสกุลเงินท้องถิ่น (THB สำหรับ TH, USD สำหรับ US) ห้ามเทียบข้าม market ตรงๆ
    - Beta ของหุ้นไทยเทียบกับ ^SET.BK (SET Index) ส่วนหุ้นสหรัฐฯ เทียบกับ ^GSPC (S&P 500)
    - peer_relative_score เทียบ P/E กับ peer ใน sector เดียวกัน (US เท่านั้นตอนนี้) เป็น Contextual
      ไม่รวมใน composite_score — ต้องมี peer ที่ดึงข้อมูลสำเร็จ ≥2 ตัวถึงจะคำนวณได้
    - price_percentile_5y เป็น percentile ของ 'ราคา' ไม่ใช่ Valuation Multiple — Contextual เท่านั้น
    - earnings_momentum_score มาจากการปรับประมาณการกำไรของนักวิเคราะห์ 30 วันล่าสุด — Contextual เท่านั้น
    - คืนค่าเป็น JSON string ของ QuantSignals — ส่งต่อกลับไปตรงๆ ห้ามแก้ไขตัวเลขในนั้น

    Args:
        ticker (str): Ticker symbol เช่น 'AAPL', 'PTT' (ห้ามมี .BK suffix — ระบบจะเติมให้)
        market (Literal["TH","US"]): 'TH' สำหรับหุ้นไทย (SET) หรือ 'US' สำหรับหุ้นอเมริกา (default)
    """
    try:
        resolved = resolve_asset(ticker, market_hint=market)
        provider_symbol = resolved.provider_symbol or ticker.strip().upper()

        autopsy_result = get_financial_autopsy(resolved)
        autopsy = autopsy_result.snapshot

        try:
            info = _get_info_cached(provider_symbol)
        except Exception as e:
            log.warning("compute_equity_quant_signals: _yf_info failed for %s: %s", provider_symbol, e)
            info = {}

        benchmark = "^SET.BK" if market == "TH" else "^GSPC"
        beta, beta_q = compute_beta(provider_symbol, benchmark=benchmark)
        volatility_pct, vol_q = compute_volatility(provider_symbol)
        mdd_pct, mdd_q = compute_mdd(provider_symbol)
        tech, tech_q = compute_technical_indicators(provider_symbol)

        company_name = info.get("shortName")

        pe = autopsy.current_pe if (autopsy and autopsy.current_pe is not None) else info.get("trailingPE")
        pb = info.get("priceToBook")
        ev_ebitda = info.get("enterpriseToEbitda")
        value_score, value_flag = compute_value_score(pe, pb, ev_ebitda)

        roe_raw = info.get("returnOnEquity")
        roe_pct = roe_raw * 100 if roe_raw is not None else None
        margin_raw = info.get("profitMargins")
        profit_margin_pct = margin_raw * 100 if margin_raw is not None else None
        fcf_debt_ratio = None
        if autopsy and autopsy.periods:
            latest = autopsy.periods[0]
            if latest.free_cash_flow is not None and latest.total_debt not in (None, 0):
                fcf_debt_ratio = latest.free_cash_flow / latest.total_debt
        quality_score, quality_flag = compute_quality_score(roe_pct, profit_margin_pct, fcf_debt_ratio)

        growth_rates, growth_flags = compute_growth_rates(autopsy.periods if autopsy else [])
        growth_score, growth_score_flag = compute_growth_score(
            growth_rates["revenue_growth_yoy_pct"], growth_rates["net_income_growth_yoy_pct"]
        )

        rsi_14 = tech.get("rsi_14") if tech else None
        macd_signal = tech.get("macd_signal") if tech else None
        ma_cross = _ma_cross_label(info.get("fiftyDayAverage"), info.get("twoHundredDayAverage"))
        momentum_score, momentum_flag = compute_momentum_score(rsi_14, macd_signal, ma_cross)

        # trailingAnnualDividendYield ต้อง *100 (decimal จริง) — ต่างจาก dividendYield ที่ percent-scaled
        # อยู่แล้ว (0.37 = 0.37%) ดู tools/market/fundamentals.py สำหรับ precedent ของ gotcha นี้
        dividend_yield_raw = info.get("trailingAnnualDividendYield")
        dividend_yield_pct = dividend_yield_raw * 100 if dividend_yield_raw is not None else None
        payout_ratio_pct = autopsy.periods[0].payout_ratio_pct if (autopsy and autopsy.periods) else None
        dividend_score, dividend_flag = compute_dividend_score(dividend_yield_pct, payout_ratio_pct)

        # debtToEquity จาก yfinance เป็นสเกล % อยู่แล้ว (150.0 = 1.5x) ใช้ตรงๆ ไม่แปลงหน่วยเพิ่ม
        de_ratio_pct = info.get("debtToEquity")
        current_ratio = info.get("currentRatio")
        solvency_score, solvency_flag = compute_solvency_score(de_ratio_pct, current_ratio)

        current_price = info.get("currentPrice")
        upside_pct, downside_pct = compute_price_target_outlook(
            current_price,
            target_mean=info.get("targetMeanPrice"),
            target_high=info.get("targetHighPrice"),
            target_low=info.get("targetLowPrice"),
        )

        adtv_local_currency, liquidity_flag = compute_trading_liquidity(
            info.get("averageVolume"), info.get("averageVolume10Day"), current_price, market
        )

        composite_score, composite_flag = compute_composite_score(
            value_score, quality_score, growth_score, momentum_score, dividend_score
        )

        # Peer/Sector Relative Valuation — Contextual เท่านั้น ไม่รวมใน composite_score
        peer_sector = info.get("sector")
        peer_metrics = fetch_peer_metrics(peer_sector, exclude_ticker=resolved.raw_symbol)
        peer_relative_score, pe_vs_peer_avg_pct, peer_count, peer_flag = compute_peer_relative_score(pe, peer_metrics)

        # Historical Price Context — Contextual เท่านั้น ไม่รวมใน composite_score (ดู docstring
        # compute_price_percentile: เป็น percentile ของราคา ไม่ใช่ Valuation Multiple)
        price_percentile_5y, price_zscore_5y, price_pctile_q = compute_price_percentile(provider_symbol)

        # Earnings Momentum & Revisions — Contextual เท่านั้น ไม่รวมใน composite_score
        revision_data, revision_fetch_flag = fetch_earnings_revision_data(provider_symbol)
        eps_revision_net_30d, eps_estimate_change_30d_pct, earnings_momentum_score, revision_score_flag = (
            compute_earnings_revision_score(revision_data)
        )

        # Cash Flow & Capital Quality
        fcf_raw = info.get("freeCashflow")
        mcap_raw = info.get("marketCap")
        fcf_yield_pct = round((fcf_raw / mcap_raw) * 100.0, 2) if (fcf_raw is not None and mcap_raw is not None and mcap_raw > 0) else None
        
        rev_raw = autopsy.periods[0].total_revenue if (autopsy and autopsy.periods) else None
        fcf_margin_pct = round((fcf_raw / rev_raw) * 100.0, 2) if (fcf_raw is not None and rev_raw is not None and rev_raw > 0) else None

        # FCF CAGR 3Y
        fcf_cagr_3y = None
        if autopsy and autopsy.periods and len(autopsy.periods) >= 4:
            fcf_latest = autopsy.periods[0].free_cash_flow
            fcf_3y_ago = autopsy.periods[3].free_cash_flow
            if fcf_latest is not None and fcf_3y_ago is not None and fcf_latest > 0 and fcf_3y_ago > 0:
                fcf_cagr_3y = round((((fcf_latest / fcf_3y_ago) ** (1.0 / 3.0)) - 1.0) * 100.0, 2)

        ocf_raw = info.get("operatingCashflow")
        net_inc_raw = autopsy.periods[0].net_income if (autopsy and autopsy.periods) else None
        ocf_to_net_income = round(ocf_raw / net_inc_raw, 2) if (ocf_raw is not None and net_inc_raw is not None and net_inc_raw > 0) else None

        ebitda_raw = info.get("ebitda")
        total_debt_raw = info.get("totalDebt") or (autopsy.periods[0].total_debt if (autopsy and autopsy.periods) else None)
        cash_raw = info.get("totalCash")
        net_debt_ebitda = round((total_debt_raw - cash_raw) / ebitda_raw, 2) if (total_debt_raw is not None and cash_raw is not None and ebitda_raw is not None and ebitda_raw > 0) else None

        latest_p = autopsy.periods[0] if (autopsy and autopsy.periods) else None
        ebit_val = latest_p.ebit if latest_p else None
        interest_exp = latest_p.interest_expense if latest_p else info.get("interestExpense")
        tax_exp = latest_p.tax_expense if latest_p else None
        pretax_inc = latest_p.income_before_tax if latest_p else None

        interest_coverage = round(ebit_val / interest_exp, 2) if (ebit_val is not None and interest_exp is not None and interest_exp > 0) else None

        # Effective Tax Rate Formula
        if tax_exp is not None and pretax_inc is not None and pretax_inc > 0:
            tax_rate = max(0.0, min(0.40, tax_exp / pretax_inc))
        else:
            tax_rate = 0.21 if market == "US" else 0.20

        # ROIC Formula: NOPAT / Invested Capital
        roic_pct = None
        tot_eq = info.get("totalStockholderEquity") or info.get("stockholderEquity")
        if ebit_val is not None and total_debt_raw is not None and tot_eq is not None and cash_raw is not None:
            inv_cap = total_debt_raw + tot_eq - cash_raw
            if inv_cap > 0:
                nopat = ebit_val * (1.0 - tax_rate)
                roic_pct = round((nopat / inv_cap) * 100.0, 2)

        fcf_quality_score, fcf_q_flag = compute_fcf_quality_score(fcf_yield_pct, ocf_to_net_income)
        debt_quality_score, debt_q_flag = compute_debt_quality_score(interest_coverage, net_debt_ebitda)

        # DCF Valuation Engine
        shares_out = info.get("sharesOutstanding")
        fcf_per_share = (fcf_raw / shares_out) if (fcf_raw is not None and shares_out is not None and shares_out > 0) else 0.0
        macro_registry = load_latest_macro_observables()

        dcf_result, dcf_flags = compute_dcf_valuation(
            ticker=resolved.raw_symbol.strip().upper(),
            market=market,
            current_price=current_price or 0.0,
            beta=beta,
            fcf_per_share=fcf_per_share,
            market_cap=mcap_raw or 0.0,
            total_debt=total_debt_raw or 0.0,
            interest_expense=interest_exp,
            tax_rate=tax_rate,
            fcf_cagr_3y=fcf_cagr_3y,
            macro_registry=macro_registry,
            forward_eps=info.get("forwardEps"),
            trailing_eps=info.get("trailingEps"),
        )

        # Smart Money & Ownership Flags
        smart_money_flags, ownership_flags = compute_smart_money_flags(provider_symbol, info)

        flags = [
            f for f in [
                value_flag, quality_flag, momentum_flag, *growth_flags, growth_score_flag,
                dividend_flag, solvency_flag, liquidity_flag, composite_flag, peer_flag,
                revision_fetch_flag or revision_score_flag, fcf_q_flag, debt_q_flag,
                *dcf_flags, *ownership_flags,
            ] if f
        ]
        for name, q in [
            ("beta", beta_q), ("volatility", vol_q), ("mdd", mdd_q), ("technical_indicators", tech_q),
            ("price_percentile", price_pctile_q),
        ]:
            if not q.is_valid:
                flags.append(f"{q.stale_reason}:{name}")

        signals = QuantSignals(
            ticker=resolved.raw_symbol.strip().upper(),
            market=market,
            company_name=company_name,
            value_score=value_score,
            quality_score=quality_score,
            momentum_score=momentum_score,
            beta=beta,
            volatility_pct=volatility_pct,
            mdd_pct=mdd_pct,
            upside_pct=upside_pct,
            downside_pct=downside_pct,
            revenue_growth_yoy_pct=growth_rates["revenue_growth_yoy_pct"],
            net_income_growth_yoy_pct=growth_rates["net_income_growth_yoy_pct"],
            growth_score=growth_score,
            dividend_yield_pct=dividend_yield_pct,
            payout_ratio_pct=payout_ratio_pct,
            dividend_score=dividend_score,
            de_ratio_pct=de_ratio_pct,
            current_ratio=current_ratio,
            solvency_score=solvency_score,
            fcf_yield_pct=fcf_yield_pct,
            fcf_margin_pct=fcf_margin_pct,
            fcf_cagr_3y=fcf_cagr_3y,
            interest_coverage=interest_coverage,
            net_debt_ebitda=net_debt_ebitda,
            roic_pct=roic_pct,
            ocf_to_net_income=ocf_to_net_income,
            fcf_quality_score=fcf_quality_score,
            debt_quality_score=debt_quality_score,
            adtv_local_currency=adtv_local_currency,
            composite_score=composite_score,
            peer_sector=peer_sector,
            peer_count=peer_count,
            pe_vs_peer_avg_pct=pe_vs_peer_avg_pct,
            peer_relative_score=peer_relative_score,
            price_percentile_5y=price_percentile_5y,
            price_zscore_5y=price_zscore_5y,
            eps_revision_net_30d=eps_revision_net_30d,
            eps_estimate_change_30d_pct=eps_estimate_change_30d_pct,
            earnings_momentum_score=earnings_momentum_score,
            dcf_result=dcf_result,
            smart_money_flags=smart_money_flags,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            data_quality_flags=flags,
        )
        return signals.model_dump_json()
    except Exception as e:
        log.warning("compute_equity_quant_signals failed for %s (%s): %s", ticker, market, e)
        return f"Error: ไม่สามารถคำนวณ Quant Signals ของ {ticker} ({market}) ได้: {e}"

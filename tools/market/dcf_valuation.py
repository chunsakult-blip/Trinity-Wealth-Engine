"""DCF / Multi-Valuation Fair Value Engine — Real WACC, CAPM, and Single Source Macro Observables.

Baseline Source Citations (For Fallbacks):
1. Thai 10Y Bond Yield: ~2.75% (Bank of Thailand / ThaiBMA Q2 2026 Baseline)
2. Thailand Country Risk Premium (CRP): ~1.75% (Damodaran Rating-based CRP Table for Baa2/BBB Sovereign Rating)
"""
from typing import Any, Optional, Dict, List, Tuple
from pathlib import Path

from langsmith import traceable

from core.logger import get_logger
from schemas.macro_schemas import MarketObservable
from schemas.micro_quant_schemas import DCFResult, DCFScenario
from tools.macro.valuation import _find_dgs10_in_observables, VALUATION_RICH_ERP_THRESHOLD

log = get_logger(__name__)


@traceable(run_type="parser")
def _extract_obs_erp(macro_registry: Dict[str, MarketObservable]) -> Tuple[float, Optional[str]]:
    """Helper ดึง obs_erp_gspc จาก macro_registry พร้อม ID"""
    obs = macro_registry.get("obs_erp_gspc")
    if obs and getattr(obs, "is_valid", True):
        try:
            return float(obs.value), obs.observable_id
        except ValueError:
            pass
    return 2.10, None


@traceable(run_type="parser")
def compute_dcf_valuation(
    ticker: str,
    market: str,
    current_price: float,
    beta: Optional[float],
    fcf_per_share: float,
    market_cap: float,
    total_debt: float,
    interest_expense: Optional[float],
    tax_rate: float,
    fcf_cagr_3y: Optional[float],
    macro_registry: Dict[str, MarketObservable],
    forward_eps: Optional[float] = None,
    trailing_eps: Optional[float] = None,
) -> Tuple[Optional[DCFResult], List[str]]:
    """คำนวณ DCF Target Price 3 ฉากทัศน์ (Bull / Base / Bear) ด้วย Real WACC"""
    flags: List[str] = []
    observable_refs: List[str] = []

    # 1. Guards: Negative FCF or Missing Beta
    if fcf_per_share <= 0:
        flags.append("negative_fcf_dcf_unavailable:dcf")
        return None, flags

    if beta is None:
        flags.append("beta_unavailable_dcf_unavailable:dcf")
        return None, flags

    if current_price <= 0:
        return None, flags

    # 2. Dynamic Observable Refs Resolution & Market CAPM
    if market == "TH":
        th_rf_obs = macro_registry.get("obs_th_10y_yield")  # Literal key
        if th_rf_obs and getattr(th_rf_obs, "is_valid", True):
            try:
                risk_free_rate = float(th_rf_obs.value)
                observable_refs.append(th_rf_obs.observable_id)
            except ValueError:
                risk_free_rate = 2.75
                flags.append("hardcoded_th_risk_free:dcf")
        else:
            risk_free_rate = 2.75  # Primary Operational Path
            flags.append("hardcoded_th_risk_free:dcf")

        th_crp_obs = macro_registry.get("obs_th_crp")
        if th_crp_obs and getattr(th_crp_obs, "is_valid", True):
            try:
                crp = float(th_crp_obs.value)
                observable_refs.append(th_crp_obs.observable_id)
            except ValueError:
                crp = 1.75
                flags.append("hardcoded_country_risk_premium:dcf")
        else:
            crp = 1.75  # Primary Operational Path (Damodaran Baa2/BBB baseline)
            flags.append("hardcoded_country_risk_premium:dcf")

        us_erp, erp_id = _extract_obs_erp(macro_registry)
        if erp_id:
            observable_refs.append(erp_id)
        erp_pct = us_erp + crp
    else:
        # US Market: Use shared _find_dgs10_in_observables with exclusions
        dgs10_val, dgs10_id = _find_dgs10_in_observables(list(macro_registry.values()))
        if dgs10_val is not None:
            risk_free_rate = dgs10_val
            if dgs10_id:
                observable_refs.append(dgs10_id)
        else:
            risk_free_rate = 4.25
            flags.append("hardcoded_us_risk_free:dcf")

        us_erp, erp_id = _extract_obs_erp(macro_registry)
        if erp_id:
            observable_refs.append(erp_id)
        erp_pct = us_erp

    # Check ERP richness threshold (1.5%)
    if erp_pct < (VALUATION_RICH_ERP_THRESHOLD * 100.0):
        flags.append("rich_market_valuation_low_erp:dcf")

    # 3. Cost of Equity (Ke) & Cost of Debt (Kd)
    ke = risk_free_rate + (beta * erp_pct)

    if total_debt > 0 and interest_expense is not None and interest_expense != 0:
        raw_kd = (abs(interest_expense) / total_debt) * 100.0
        kd = max(2.0, min(15.0, raw_kd))
        if raw_kd < 2.0 or raw_kd > 15.0:
            flags.append("kd_clamped:dcf")
    else:
        kd = 5.0
        flags.append("hardcoded_cost_of_debt:dcf")

    # 4. Capital Structure Weighting (Real WACC)
    v = market_cap + total_debt if (market_cap is not None and market_cap > 0) else total_debt
    e_weight = (market_cap / v) if (market_cap and v > 0) else 1.0
    d_weight = (total_debt / v) if (total_debt and v > 0) else 0.0

    wacc_pct = round((e_weight * ke) + (d_weight * kd * (1.0 - tax_rate)), 2)
    wacc_dec = wacc_pct / 100.0

    # 5. Projection & Gordon Growth Model (Single Outside Loop Flag Check)
    g_terminal = min(0.025, risk_free_rate / 100.0)
    if wacc_dec <= g_terminal:
        flags.append("wacc_below_terminal_growth:dcf")

    bull_g = min(0.15, (fcf_cagr_3y / 100.0 if fcf_cagr_3y is not None else 0.10))
    bear_g = 0.0

    if (
        forward_eps is not None and trailing_eps is not None
        and trailing_eps != 0
        and abs(trailing_eps) > 0.01
    ):
        yoy_eps_growth = (forward_eps - trailing_eps) / abs(trailing_eps)
        base_g = max(-0.05, min(0.20, yoy_eps_growth))
        flags.append("eps_proxy_base_growth:dcf")
    else:
        base_g = 0.05
        flags.append("generic_base_growth_assumption:dcf")

    scenarios: Dict[str, DCFScenario] = {}
    for key, g in [("bull", bull_g), ("base", base_g), ("bear", bear_g)]:
        pv_fcf = sum([(fcf_per_share * ((1.0 + g) ** t)) / ((1.0 + wacc_dec) ** t) for t in range(1, 6)])
        fcf_5 = fcf_per_share * ((1.0 + g) ** 5)

        if wacc_dec > g_terminal:
            terminal_val = (fcf_5 * (1.0 + g_terminal)) / (wacc_dec - g_terminal)
        else:
            terminal_val = 0.0

        pv_terminal = terminal_val / ((1.0 + wacc_dec) ** 5)
        target_price = round(pv_fcf + pv_terminal, 2)
        upside = round(((target_price - current_price) / current_price) * 100.0, 1)
        mos = round(((target_price - current_price) / target_price) * 100.0, 1)
        scenarios[key] = DCFScenario(target_price=target_price, upside_pct=upside, margin_of_safety_pct=mos)

    # 6. Verdict via MoS
    base_tp = scenarios["base"].target_price
    if current_price <= base_tp * 0.80:
        verdict = "undervalued"
    elif current_price >= base_tp * 1.15:
        verdict = "overvalued"
    else:
        verdict = "fairly_valued"

    result = DCFResult(
        wacc_pct=wacc_pct,
        cost_of_equity_pct=round(ke, 2),
        cost_of_debt_pct=round(kd, 2),
        risk_free_rate_pct=risk_free_rate,
        erp_pct=erp_pct,
        observable_refs=observable_refs,
        scenarios=scenarios,
        valuation_verdict=verdict,
    )
    return result, flags

"""Unit tests for DCF Valuation Engine & Smart Money Flags."""
import pytest
from schemas.macro_schemas import MarketObservable
from tools.market.dcf_valuation import compute_dcf_valuation, _extract_obs_erp
from tools.market.ownership import compute_smart_money_flags


def _erp_observable(value: str = "2.10") -> MarketObservable:
    return MarketObservable(
        observable_id="obs_erp_gspc",
        asset_bucket="equities",
        region="US",
        indicator="S&P 500 ERP",
        value=value,
        unit="%",
        observed_at="2026-08-06",
        source_file="test",
        provider="test",
        is_valid=True,
        observable_type="valuation",
    )


def _dgs10_observable(value: str = "4.25") -> MarketObservable:
    # Real registry IDs are date-suffixed/dynamic (see tools/macro/evaluation.py),
    # never the literal string "obs_dgs10" — use a realistic ID so this test actually
    # exercises the fuzzy resolver instead of a coincidental exact-string match.
    return MarketObservable(
        observable_id="obs_fred_dgs10_20260806",
        asset_bucket="fixed_income",
        region="US",
        indicator="10Y Treasury Yield",
        value=value,
        unit="%",
        observed_at="2026-08-06",
        source_file="test",
        provider="test",
        is_valid=True,
        observable_type="rates",
    )


def test_dcf_valuation_basic_us():
    macro_reg = {
        "obs_erp_gspc": _erp_observable(),
        "obs_fred_dgs10_20260806": _dgs10_observable(),
    }

    result, flags = compute_dcf_valuation(
        ticker="AAPL",
        market="US",
        current_price=180.0,
        beta=1.1,
        fcf_per_share=6.5,
        market_cap=2800000000000.0,
        total_debt=100000000000.0,
        interest_expense=3000000000.0,
        tax_rate=0.15,
        fcf_cagr_3y=8.5,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert result.valuation_verdict in ("undervalued", "fairly_valued", "overvalued")
    assert result.wacc_pct > 0
    assert result.cost_of_equity_pct > 0
    assert result.cost_of_debt_pct > 0
    assert "obs_erp_gspc" in result.observable_refs
    assert "obs_fred_dgs10_20260806" in result.observable_refs
    assert "generic_base_growth_assumption:dcf" in flags


def test_dcf_valuation_beta_none_guard():
    macro_reg = {}
    result, flags = compute_dcf_valuation(
        ticker="NEWIPO",
        market="US",
        current_price=25.0,
        beta=None,
        fcf_per_share=2.0,
        market_cap=500000000.0,
        total_debt=0.0,
        interest_expense=None,
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is None
    assert "beta_unavailable_dcf_unavailable:dcf" in flags


def test_dcf_valuation_negative_fcf_guard():
    macro_reg = {}
    result, flags = compute_dcf_valuation(
        ticker="UNPROFITABLE",
        market="US",
        current_price=10.0,
        beta=1.5,
        fcf_per_share=-0.50,
        market_cap=200000000.0,
        total_debt=50000000.0,
        interest_expense=2000000.0,
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is None
    assert "negative_fcf_dcf_unavailable:dcf" in flags


def test_dcf_valuation_th_fallback_path():
    """TH market with no obs_th_10y_yield/obs_th_crp in registry -> primary operational fallback."""
    macro_reg = {"obs_erp_gspc": _erp_observable()}

    result, flags = compute_dcf_valuation(
        ticker="PTT.BK",
        market="TH",
        current_price=35.0,
        beta=0.9,
        fcf_per_share=3.0,
        market_cap=900000000000.0,
        total_debt=400000000000.0,
        interest_expense=8000000000.0,
        tax_rate=0.20,
        fcf_cagr_3y=4.0,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert result.risk_free_rate_pct == 2.75
    assert "hardcoded_th_risk_free:dcf" in flags
    assert "hardcoded_country_risk_premium:dcf" in flags
    assert "obs_dgs10" not in result.observable_refs  # US-only observable must never leak into TH refs


def test_dcf_valuation_th_registry_hit_path():
    """TH market where obs_th_10y_yield/obs_th_crp are present -> dynamic refs, no hardcode flags."""
    th_rf = MarketObservable(
        observable_id="obs_th_10y_yield",
        asset_bucket="fixed_income",
        region="TH",
        indicator="Thailand 10Y Government Bond Yield",
        value="2.60",
        unit="%",
        observed_at="2026-08-06",
        source_file="test",
        provider="test",
        is_valid=True,
        observable_type="rates",
    )
    th_crp = MarketObservable(
        observable_id="obs_th_crp",
        asset_bucket="risk",
        region="TH",
        indicator="Thailand Country Risk Premium",
        value="1.75",
        unit="%",
        observed_at="2026-08-06",
        source_file="test",
        provider="test",
        is_valid=True,
        observable_type="derived_ratio",
    )
    macro_reg = {
        "obs_erp_gspc": _erp_observable(),
        "obs_th_10y_yield": th_rf,
        "obs_th_crp": th_crp,
    }

    result, flags = compute_dcf_valuation(
        ticker="PTT.BK",
        market="TH",
        current_price=35.0,
        beta=0.9,
        fcf_per_share=3.0,
        market_cap=900000000000.0,
        total_debt=400000000000.0,
        interest_expense=8000000000.0,
        tax_rate=0.20,
        fcf_cagr_3y=4.0,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert result.risk_free_rate_pct == 2.60
    assert "hardcoded_th_risk_free:dcf" not in flags
    assert "hardcoded_country_risk_premium:dcf" not in flags
    assert "obs_th_10y_yield" in result.observable_refs
    assert "obs_th_crp" in result.observable_refs


def test_dcf_valuation_kd_clamped_flag():
    """interest_expense/total_debt yielding raw_kd outside [2, 15] must clamp and flag."""
    macro_reg = {"obs_erp_gspc": _erp_observable(), "obs_fred_dgs10_20260806": _dgs10_observable()}

    result, flags = compute_dcf_valuation(
        ticker="DISTRESSED",
        market="US",
        current_price=5.0,
        beta=1.8,
        fcf_per_share=0.5,
        market_cap=100000000.0,
        total_debt=50000000.0,
        interest_expense=15000000.0,  # 30% raw Kd -> clamps to 15%
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert result.cost_of_debt_pct == 15.0
    assert "kd_clamped:dcf" in flags


def test_dcf_valuation_kd_fallback_flag():
    macro_reg = {"obs_erp_gspc": _erp_observable(), "obs_fred_dgs10_20260806": _dgs10_observable()}

    result, flags = compute_dcf_valuation(
        ticker="NODEBT",
        market="US",
        current_price=50.0,
        beta=1.0,
        fcf_per_share=2.0,
        market_cap=1000000000.0,
        total_debt=0.0,
        interest_expense=None,
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert result.cost_of_debt_pct == 5.0
    assert "hardcoded_cost_of_debt:dcf" in flags


def test_dcf_valuation_rich_erp_warning_flag():
    """ERP below VALUATION_RICH_ERP_THRESHOLD (1.5%) must trigger the low-ERP warning."""
    macro_reg = {"obs_erp_gspc": _erp_observable(value="1.00"), "obs_fred_dgs10_20260806": _dgs10_observable()}

    result, flags = compute_dcf_valuation(
        ticker="RICHMKT",
        market="US",
        current_price=100.0,
        beta=1.0,
        fcf_per_share=3.0,
        market_cap=1000000000.0,
        total_debt=100000000.0,
        interest_expense=4000000.0,
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert "rich_market_valuation_low_erp:dcf" in flags


def test_dcf_valuation_wacc_below_terminal_growth_flag_not_duplicated():
    """When WACC <= g_terminal, the warning flag must appear exactly once (idempotent, not per-scenario)."""
    macro_reg = {"obs_erp_gspc": _erp_observable(value="0.10"), "obs_fred_dgs10_20260806": _dgs10_observable(value="0.50")}

    result, flags = compute_dcf_valuation(
        ticker="ULTRALOWRATE",
        market="US",
        current_price=50.0,
        beta=0.0,
        fcf_per_share=1.0,
        market_cap=1000000000.0,
        total_debt=0.0,
        interest_expense=None,
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert flags.count("wacc_below_terminal_growth:dcf") == 1


def test_dcf_valuation_verdict_thresholds():
    """Verdict must follow current_price vs base-case target price at the agreed 20%/15% bands."""
    macro_reg = {"obs_erp_gspc": _erp_observable(), "obs_fred_dgs10_20260806": _dgs10_observable()}

    result, _ = compute_dcf_valuation(
        ticker="VERDICTCHECK",
        market="US",
        current_price=50.0,
        beta=1.0,
        fcf_per_share=6.0,
        market_cap=1000000000.0,
        total_debt=0.0,
        interest_expense=None,
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is not None
    base_tp = result.scenarios["base"].target_price
    if result.valuation_verdict == "undervalued":
        assert 50.0 <= base_tp * 0.80
    elif result.valuation_verdict == "overvalued":
        assert 50.0 >= base_tp * 1.15
    else:
        assert base_tp * 0.80 < 50.0 < base_tp * 1.15


def test_smart_money_flags():
    mock_info = {
        "heldPercentInstitutions": 0.65,
        "heldPercentInsiders": 0.05,
        "shortPercentOfFloat": 0.03,
    }
    res, flags = compute_smart_money_flags("AAPL", mock_info)
    assert res.institutional_ownership_pct == 65.0
    assert res.insider_ownership_pct == 5.0
    assert res.short_interest_pct == 3.0
    assert "10b51_unfiltered:insider_signal" in flags


def test_kd_uses_abs_when_interest_expense_negative():
    """Negative interest expense must be treated with abs() so raw_kd=7.5% without hardcode fallback."""
    macro_reg = {"obs_erp_gspc": _erp_observable(), "obs_fred_dgs10_20260806": _dgs10_observable()}

    result, flags = compute_dcf_valuation(
        ticker="NEGINTEREST",
        market="US",
        current_price=100.0,
        beta=1.0,
        fcf_per_share=5.0,
        market_cap=1000000000.0,
        total_debt=2000.0,
        interest_expense=-150.0,  # abs(-150) / 2000 * 100 = 7.5%
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert result.cost_of_debt_pct == 7.5
    assert "hardcoded_cost_of_debt:dcf" not in flags


def test_base_g_uses_eps_proxy_when_available():
    """When forward_eps and trailing_eps are available, base_g must use EPS YoY growth and emit eps_proxy_base_growth:dcf."""
    macro_reg = {"obs_erp_gspc": _erp_observable(), "obs_fred_dgs10_20260806": _dgs10_observable()}

    result, flags = compute_dcf_valuation(
        ticker="EPSGROWTH",
        market="US",
        current_price=100.0,
        beta=1.0,
        fcf_per_share=5.0,
        market_cap=1000000000.0,
        total_debt=0.0,
        interest_expense=None,
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
        forward_eps=10.0,
        trailing_eps=8.0,  # YoY = (10 - 8)/8 = 0.25 -> clamped to 0.20
    )

    assert result is not None
    assert "eps_proxy_base_growth:dcf" in flags
    assert "generic_base_growth_assumption:dcf" not in flags


def test_base_g_falls_back_when_eps_missing():
    """When EPS numbers are missing, base_g must fall back to 5% and emit generic_base_growth_assumption:dcf."""
    macro_reg = {"obs_erp_gspc": _erp_observable(), "obs_fred_dgs10_20260806": _dgs10_observable()}

    result, flags = compute_dcf_valuation(
        ticker="NOEPS",
        market="US",
        current_price=100.0,
        beta=1.0,
        fcf_per_share=5.0,
        market_cap=1000000000.0,
        total_debt=0.0,
        interest_expense=None,
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert "generic_base_growth_assumption:dcf" in flags
    assert "eps_proxy_base_growth:dcf" not in flags


def test_hardcoded_us_risk_free_flag_when_dgs10_missing():
    """When DGS10 observable is missing from registry for US market, hardcoded_us_risk_free:dcf must be emitted."""
    macro_reg = {"obs_erp_gspc": _erp_observable()}  # missing DGS10

    result, flags = compute_dcf_valuation(
        ticker="NODGS10",
        market="US",
        current_price=100.0,
        beta=1.0,
        fcf_per_share=5.0,
        market_cap=1000000000.0,
        total_debt=0.0,
        interest_expense=None,
        tax_rate=0.21,
        fcf_cagr_3y=None,
        macro_registry=macro_reg,
    )

    assert result is not None
    assert result.risk_free_rate_pct == 4.25
    assert "hardcoded_us_risk_free:dcf" in flags


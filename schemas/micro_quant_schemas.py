"""Schemas สำหรับ Equity Intel Pipeline (Micro Quant Agent) — มิเรอร์โครงสร้างของ schemas/macro_schemas.py

แยกชั้นชัดเจน: QuantSignals (deterministic ล้วน, ห้าม LLM แตะ) vs EquitySentimentContext/EquityNarrativeOutput
(LLM-derived — categorical/text เท่านั้น ไม่มี numeric field ที่ดูเหมือน deterministic)
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DCFScenario(BaseModel):
    target_price: float
    upside_pct: float
    margin_of_safety_pct: float


class DCFResult(BaseModel):
    wacc_pct: float
    cost_of_equity_pct: float
    cost_of_debt_pct: float
    risk_free_rate_pct: float
    erp_pct: float
    observable_refs: list[str] = Field(default_factory=list)
    scenarios: dict[str, DCFScenario]
    valuation_verdict: Literal["undervalued", "fairly_valued", "overvalued"]


class SmartMoneyFlags(BaseModel):
    insider_signal: Literal["buying", "selling", "neutral"] = "neutral"
    insider_buy_count_90d: int = 0
    insider_sell_count_90d: int = 0
    institutional_ownership_pct: Optional[float] = None
    insider_ownership_pct: Optional[float] = None
    short_interest_pct: Optional[float] = None
    short_squeeze_risk: bool = False
    overall_smart_money_flag: Literal["bullish_signal", "bearish_signal", "neutral"] = "neutral"


class QuantSignals(BaseModel):
    """ผลลัพธ์จาก compute_equity_quant_signals — deterministic 100% ไม่มี field ไหนมาจาก LLM"""
    ticker: str
    market: Literal["TH", "US"]
    company_name: Optional[str] = Field(default=None, description="ชื่อบริษัทเต็ม (yfinance shortName) — ใช้ปรับปรุงคุณภาพ Vault search และหัวรายงาน")
    value_score: Optional[float] = Field(default=None, description="0-100, None ถ้าข้อมูลไม่พอ (เช่น P/E ติดลบ)")
    quality_score: Optional[float] = None
    momentum_score: Optional[float] = Field(
        default=None,
        description="วัดความแรงของโมเมนตัมขาขึ้นเชิงเทคนิค ไม่ใช่คำแนะนำซื้อ — ดู tools/market/quant_scoring.py",
    )
    beta: Optional[float] = None
    volatility_pct: Optional[float] = None
    mdd_pct: Optional[float] = None
    upside_pct: Optional[float] = None
    downside_pct: Optional[float] = None
    # Growth
    revenue_growth_yoy_pct: Optional[float] = None
    net_income_growth_yoy_pct: Optional[float] = None
    growth_score: Optional[float] = None
    # Dividend
    dividend_yield_pct: Optional[float] = None
    payout_ratio_pct: Optional[float] = None
    dividend_score: Optional[float] = None
    # Solvency — Risk Gate แยกจาก Composite Score (ดู compute_solvency_score docstring)
    de_ratio_pct: Optional[float] = Field(default=None, description="debtToEquity จาก yfinance ตรงๆ (150.0 = D/E 1.5x)")
    current_ratio: Optional[float] = None
    solvency_score: Optional[float] = None
    # Cash Flow & Capital Quality
    fcf_yield_pct: Optional[float] = None
    fcf_margin_pct: Optional[float] = None
    fcf_cagr_3y: Optional[float] = None
    interest_coverage: Optional[float] = None
    net_debt_ebitda: Optional[float] = None
    roic_pct: Optional[float] = None
    ocf_to_net_income: Optional[float] = None
    fcf_quality_score: Optional[float] = None
    debt_quality_score: Optional[float] = None
    # Trading Liquidity
    adtv_local_currency: Optional[float] = Field(
        default=None,
        description="มูลค่าซื้อขายเฉลี่ยต่อวัน สกุลท้องถิ่น (THB สำหรับ TH, USD สำหรับ US) — ไม่ใช่ USD-normalized ห้ามเทียบข้าม market ตรงๆ",
    )
    # Composite
    composite_score: Optional[float] = Field(
        default=None,
        description="Weighted: Value25/Quality25/Growth25/Momentum15/Dividend10 (re-normalize ถ้าขาดมิติ) — Solvency ไม่รวม (risk gate แยก)",
    )
    # Peer/Sector Relative Valuation — Contextual เท่านั้น ไม่รวมใน composite_score
    peer_sector: Optional[str] = None
    peer_count: Optional[int] = None
    pe_vs_peer_avg_pct: Optional[float] = Field(default=None, description="บวก=แพงกว่า peer เฉลี่ย, ลบ=ถูกกว่า")
    peer_relative_score: Optional[float] = None
    # Historical Price Context — Percentile/Z-score ของ 'ราคา' ไม่ใช่ Valuation Multiple (yfinance
    # ไม่มี point-in-time fundamentals พอคำนวณ P/E percentile ย้อนหลังได้) — Contextual เท่านั้น
    price_percentile_5y: Optional[float] = Field(default=None, description="0-100, เปอร์เซ็นไทล์ของราคาปัจจุบันเทียบช่วง 5 ปี (ราคา ไม่ใช่ P/E)")
    price_zscore_5y: Optional[float] = None
    # Earnings Momentum & Revisions — Contextual เท่านั้น ไม่รวมใน composite_score
    eps_revision_net_30d: Optional[int] = Field(default=None, description="จำนวนนักวิเคราะห์ที่ปรับกำไรขึ้น ลบด้วยปรับลง ใน 30 วันล่าสุด (ปีบัญชีปัจจุบัน)")
    eps_estimate_change_30d_pct: Optional[float] = None
    earnings_momentum_score: Optional[float] = None
    # DCF Engine & Valuation
    dcf_result: Optional[DCFResult] = None
    # Smart Money Signals
    smart_money_flags: Optional[SmartMoneyFlags] = None
    evaluated_at: str = Field(description="ISO format string (ไม่ใช่ datetime object)")
    data_quality_flags: list[str] = Field(
        default_factory=list,
        description="เช่น 'insufficient_trading_history:beta', 'negative_earnings:pe_undefined'",
    )


class EquitySentimentContext(BaseModel):
    """มิเรอร์ NarrativeContext (schemas/macro_schemas.py) — categorical ไม่ใช่ raw float เพื่อไม่ให้
    ดูเหมือนตัวเลข deterministic ทั้งที่เป็นการประเมินเชิงคุณภาพของ LLM"""
    evaluated_at: str
    market_sentiment: Literal["bullish", "neutral", "bearish"]
    key_themes: list[str] = Field(default_factory=list)
    tail_risks: list[str] = Field(default_factory=list)
    sources_summary: str
    report_references: list[dict[str, Any]] = Field(default_factory=list)


class EquityNarrativeOutput(BaseModel):
    """Schema แคบที่ equity_synthesizer ผูกกับ LLM ตัวสุดท้าย — ไม่มี numeric field ให้แตะเลย"""
    narrative_analysis: str
    base_case_summary: str


class MicroQuantOutput(BaseModel):
    """ผลลัพธ์สุดท้ายของ equity_intel pipeline — numeric fields มาจาก Python เท่านั้น,
    text fields มาจาก LLM (EquityNarrativeOutput) เท่านั้น ไม่มีการปนกัน"""
    ticker: str
    market: Literal["TH", "US"]
    analysis_date: str
    quant_signals: QuantSignals
    sentiment_context: EquitySentimentContext
    narrative_analysis: str
    base_case_summary: str
    generated_by: str = "equity_intel"

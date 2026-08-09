"""มิเรอร์ tools/macro/report_formatter.py::format_macro_strategy_report สำหรับ equity_intel pipeline

Python เขียนตัวเลขทั้งหมดจาก quant_signals ตรงๆ — LLM (equity_synthesizer) ไม่มีโอกาสแตะตัวเลข
ในขั้นตอนนี้เลย มีแค่ narrative_analysis/base_case_summary ที่เป็น text จาก LLM
"""
from datetime import datetime

from schemas.micro_quant_schemas import MicroQuantOutput
from .core import _fmt_large

_SENTIMENT_LABELS = {"bullish": "🟢 Bullish", "bearish": "🔴 Bearish", "neutral": "⚪ Neutral"}


def _fmt(value) -> str:
    return "N/A" if value is None else str(value)


DATA_QUALITY_FLAG_TRANSLATIONS: dict[str, tuple[str, str]] = {
    # dcf_valuation.py
    "negative_fcf_dcf_unavailable:dcf": (
        "ไม่สามารถคำนวณ DCF ได้ (FCF ติดลบ)",
        "กระแสเงินสดเสรีเป็นลบ จึงไม่สามารถประเมินมูลค่าด้วย DCF ได้",
    ),
    "beta_unavailable_dcf_unavailable:dcf": (
        "ไม่สามารถคำนวณ DCF ได้ (ไม่พบค่า Beta)",
        "ไม่มีข้อมูลความผันผวนเทียบกับตลาด (Beta) ทำให้คำนวณ Cost of Equity ไม่ได้",
    ),
    "hardcoded_th_risk_free:dcf": (
        "ใช้อัตราดอกเบี้ย Risk-Free ไทยอ้างอิง (2.75%)",
        "ไม่พบข้อมูลพันธบัตรรัฐบาลไทย 10 ปีล่าสุด จึงใช้อัตราดอกเบี้ยสำรอง",
    ),
    "hardcoded_country_risk_premium:dcf": (
        "ใช้ Country Risk Premium อ้างอิง (1.75%)",
        "ใช้อัตราความเสี่ยงประเทศสำรองตามตาราง Damodaran",
    ),
    "hardcoded_us_risk_free:dcf": (
        "ใช้อัตราดอกเบี้ย Risk-Free อ้างอิง (4.25%)",
        "ไม่พบข้อมูลอัตราดอกเบี้ยพันธบัตรรัฐบาลสหรัฐฯ 10 ปีในระบบ จึงใช้อัตราดอกเบี้ยสำรอง",
    ),
    "rich_market_valuation_low_erp:dcf": (
        "Equity Risk Premium (ERP) ของตลาดค่อนข้างต่ำ (<1.5%)",
        "ผลตอบแทนชดเชยความเสี่ยงหุ้นเทียบกับพันธบัตรแคบลง สะท้อนสภาวะตลาด Valuation ตึงตัว",
    ),
    "kd_clamped:dcf": (
        "จำกัดช่วง Cost of Debt (2%-15%)",
        "ปรับอัตราดอกเบี้ยจ่ายให้อยู่ในกรอบมาตรฐานการคำนวณ",
    ),
    "hardcoded_cost_of_debt:dcf": (
        "ใช้ Cost of Debt อ้างอิง (5.0%)",
        "ไม่พบข้อมูลดอกเบี้ยจ่ายจริง จึงใช้ค่าประมาณการสำรอง",
    ),
    "wacc_below_terminal_growth:dcf": (
        "WACC ต่ำกว่าอัตราเติบโต Terminal Growth",
        "WACC มีค่าน้อยกว่าหรือเท่ากับอัตราการเติบโตระยะยาว ไม่สามารถใช้ Gordon Growth Model โดยตรง",
    ),
    "eps_proxy_base_growth:dcf": (
        "ใช้ YoY EPS Growth เป็นตัวแทน FCF Base Growth",
        "ประมาณการการเติบโต 5 ปีของ Free Cash Flow จากอัตราการเติบโต EPS",
    ),
    "generic_base_growth_assumption:dcf": (
        "ใช้ Base Growth อ้างอิง 5.0%",
        "ไม่พบข้อมูล EPS Growth จึงใช้สมมติฐานการเติบโตมาตรฐาน 5%",
    ),
    # ownership.py
    "10b51_unfiltered:insider_signal": (
        "ข้อมูล Insider ไม่ได้แยกแผน 10b5-1",
        "รายการซื้อขายของผู้บริหารรวมทั้งการซื้อขายตามแผนล่วงหน้าและแบบสมัครใจ",
    ),
    "insider_date_unavailable:insider_signal": (
        "ไม่มีข้อมูลวันที่ในรายการ Insider",
        "ไม่สามารถกรองรายการเฉพาะ 90 วันล่าสุดได้",
    ),
    # quant_scoring.py
    "negative_earnings:pe_undefined": (
        "ไม่สามารถคำนวณ P/E ได้ (กำไรติดลบ)",
        "บริษัทมีผลขาดทุนสุทธิ ทำให้ไม่สามารถประเมินมูลค่าผ่าน P/E Ratio ได้",
    ),
    "missing_growth_data:growth": (
        "ข้อมูลการเติบโตไม่เพียงพอ",
        "ขาดข้อมูลรายได้หรือกำไรย้อนหลังสำหรับคำนวณ Growth Score",
    ),
    "missing_dividend_data:dividend": (
        "ข้อมูลเงินปันผลไม่เพียงพอ",
        "ขาดข้อมูลการจ่ายเงินปันผลหรืออัตราตอบแทนปันผล",
    ),
    "unsustainable_payout:dividend": (
        "อัตราจ่ายปันผลสูงเกินความยั่งยืน (>100%)",
        "เงินปันผลที่จ่ายสูงกว่ากำไรสุทธิ มีความเสี่ยงที่จะลดการจ่ายปันผลในอนาคต",
    ),
    "missing_solvency_data:solvency": (
        "ข้อมูลความมั่นคงทางการเงินไม่เพียงพอ",
        "ขาดข้อมูลงบการเงินสำหรับคำนวณ Solvency Score",
    ),
    "high_leverage_risk:solvency": (
        "ความเสี่ยงภาระหนี้สินสูง",
        "สัดส่วนหนี้สินต่อทุน (D/E) หรือ Net Debt/EBITDA อยู่ในระดับสูงกว่ามาตรฐาน",
    ),
    "missing_liquidity_data:liquidity": (
        "ข้อมูลสภาพคล่องการซื้อขายไม่เพียงพอ",
        "ไม่พบข้อมูลมูลค่าการซื้อขายเฉลี่ยรายวัน (ADTV)",
    ),
    "low_liquidity:liquidity": (
        "สภาพคล่องการซื้อขายค่อนข้างต่ำ",
        "มูลค่าการซื้อขายเฉลี่ยรายวันต่ำกว่าเกณฑ์ อาจมีขีดจำกัดในการเข้าซื้อหรือขายออก",
    ),
    "insufficient_dimensions:composite": (
        "มิติการประเมินไม่ครบถ้วน",
        "มิติคำนวณ Score ไม่ครบ จึงมีการปรับ re-normalize น้ำหนักที่เหลือ",
    ),
    "missing_fcf_quality_data:fcf_quality": (
        "ข้อมูลคุณภาพกระแสเงินสดไม่เพียงพอ",
        "ขาดข้อมูลงบกระแสเงินสดสำหรับประเมิน FCF Quality",
    ),
    "missing_debt_quality_data:debt_quality": (
        "ข้อมูลคุณภาพหนี้สินไม่เพียงพอ",
        "ขาดข้อมูลดอกเบี้ยจ่ายหรือภาระหนี้สำหรับประเมิน Debt Quality",
    ),
    "high_debt_risk:debt_quality": (
        "ความเสี่ยงคุณภาพหนี้สินสูง",
        "ความสามารถในการชำระดอกเบี้ย (Interest Coverage) ต่ำกว่าเกณฑ์ความปลอดภัย",
    ),
    # peer_valuation.py
    "missing_own_pe:peer_relative": (
        "ไม่สามารถเปรียบเทียบ P/E กับกลุ่มได้ (ไม่มี P/E ตนเอง)",
        "หุ้นมี P/E ติดลบหรือไม่พบค่า P/E จึงไม่สามารถเปรียบเทียบกับกลุ่มอุตสาหกรรมได้",
    ),
    "insufficient_peers:peer_relative": (
        "จำนวนหุ้นเปรียบเทียบในกลุ่มไม่เพียงพอ",
        "มีหุ้นคู่แข่งในกลุ่มเดียวกันน้อยกว่าเกณฑ์ที่ใช้ประเมิน Peer Relative Score",
    ),
    # quant_engine.py
    "insufficient_periods:growth": (
        "รอบข้อมูลงบการเงินย้อนหลังไม่เพียงพอ",
        "ข้อมูลงบการเงินในอดีตมีน้อยกว่า 2 ช่วงเวลา ไม่สามารถคำนวณ YoY Growth ได้",
    ),
    "non_annual_period_gap:growth": (
        "ระยะเวลาเปรียบเทียบงบการเงินไม่ใช่งวดปีเต็ม",
        "งวดเวลาของข้อมูลเปรียบเทียบไม่อยู่ในรอบ 12 เดือนเต็ม",
    ),
}

_STALE_REASON_LABELS = {
    "insufficient_trading_history": "ประวัติราคาซื้อขายไม่เพียงพอ",
    "fetch_error": "ดึงข้อมูลย้อนหลังไม่สำเร็จ",
    "zero_benchmark_variance": "ความผันผวนของดัชนีอ้างอิงเป็นศูนย์",
}

_METRIC_LABELS_TH = {
    "beta": "Beta",
    "volatility": "Volatility",
    "mdd": "Max Drawdown",
    "technical_indicators": "ตัวชี้วัดทางเทคนิค (Momentum)",
    "price_percentile": "Price Percentile",
}


def _translate_flag(raw: str) -> str:
    """แปลง raw flag code ให้เป็นคำอธิบายภาษาไทยพร้อมต่อท้ายด้วย (`raw_code`)"""
    if raw in DATA_QUALITY_FLAG_TRANSLATIONS:
        label, subtext = DATA_QUALITY_FLAG_TRANSLATIONS[raw]
        return f"- **{label}**: {subtext} (`{raw}`)"

    if ":" in raw:
        code, domain = raw.split(":", 1)
        reason_th = _STALE_REASON_LABELS.get(code)
        metric_th = _METRIC_LABELS_TH.get(domain)
        if reason_th and metric_th:
            return f"- **ไม่สามารถคำนวณ {metric_th} ได้**: {reason_th} (`{raw}`)"

        clean_code = code.replace("_", " ").title()
        return f"- **{clean_code}** ({domain.upper()}) (`{raw}`)"

    return f"- **{raw.replace('_', ' ')}** (`{raw}`)"


def format_equity_analysis_report(output: MicroQuantOutput) -> str:
    """Build markdown report จาก MicroQuantOutput — ตัวเลขทั้งหมดมาจาก quant_signals โดยตรง (Python)"""
    today = output.analysis_date
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    q = output.quant_signals
    s = output.sentiment_context
    display_name = f"{q.company_name} ({output.ticker})" if q.company_name else output.ticker

    benchmark_label = "^SET.BK" if output.market == "TH" else "^GSPC"
    currency_label = "THB" if output.market == "TH" else "USD"

    lines = [
        "---",
        f"title: {output.ticker} Equity Analysis {today}",
        "entity_type: equity_analysis",
        f"ticker: {output.ticker}",
        f"market: {output.market}",
        f"date: {today}",
        f"last_updated: {now}",
        f"generated_by: {output.generated_by}",
        f"tags: [stock_analysis, {output.ticker.lower()}, market_{output.market.lower()}, equity_quant]",
        "---\n",
        f"# 📊 บทวิเคราะห์เชิงปริมาณ: {display_name} ({output.market}) — {today}\n",
        f"> **Market Sentiment:** {_SENTIMENT_LABELS.get(s.market_sentiment, s.market_sentiment)}",
        f"> **ประเมินเมื่อ (Evaluated At):** {q.evaluated_at}\n",
        f"## 🏆 Composite Score: {_fmt(q.composite_score)} / 100\n",
        "> Weighted: Value 25% + Quality 25% + Growth 25% + Momentum 15% + Dividend 10% "
        "(ข้ามมิติที่ไม่มีข้อมูลแล้ว re-normalize weight ที่เหลือ — **ไม่รวม Solvency, Peer/Sector, "
        "Historical Price, Earnings Momentum** ดูตัวชี้วัด Contextual ด้านล่างประกอบ)\n",
        "## 🔢 Quant Signals (Deterministic — คำนวณจาก Python ล้วน)\n",
        "| Metric | Value | หมายเหตุ |",
        "|---|---|---|",
        f"| **Value Score** | {_fmt(q.value_score)} | 0-100, ยิ่งสูงยิ่งถูก (Valuation) |",
        f"| **Quality Score** | {_fmt(q.quality_score)} | 0-100, ยิ่งสูงยิ่งมีคุณภาพกิจการดี |",
        f"| **Growth Score** | {_fmt(q.growth_score)} | 0-100, จาก Revenue/Net Income Growth YoY |",
        f"| **Momentum Score** | {_fmt(q.momentum_score)} | 0-100, วัดความแรงขาขึ้นเชิงเทคนิค (ไม่ใช่คำแนะนำซื้อ — RSI สูงอาจหมายถึง Overbought) |",
        f"| **Dividend Score** | {_fmt(q.dividend_score)} | 0-100 — ⚠️ Yield สูงผิดปกติอาจเป็น Value Trap ดู Payout Ratio ประกอบ |",
        f"| **Beta** | {_fmt(q.beta)} | เทียบ {benchmark_label} |",
        f"| **Volatility (Annualized)** | {_fmt(q.volatility_pct)}% | |",
        f"| **Max Drawdown** | {_fmt(q.mdd_pct)}% | |",
        f"| **Upside (Target High)** | {_fmt(q.upside_pct)}% | |",
        f"| **Downside (Target Low)** | {_fmt(q.downside_pct)}% | |",
        "",
        "### 📈 Growth Signals\n",
        f"- Revenue Growth YoY: {_fmt(q.revenue_growth_yoy_pct)}%",
        f"- Net Income Growth YoY: {_fmt(q.net_income_growth_yoy_pct)}%",
        "",
        "### 💰 Dividend\n",
        f"- Dividend Yield: {_fmt(q.dividend_yield_pct)}%",
        f"- Payout Ratio: {_fmt(q.payout_ratio_pct)}%",
        "",
        "### 💵 Cash Flow & Capital Quality\n",
        f"- FCF Yield: {_fmt(q.fcf_yield_pct)}%",
        f"- FCF Margin: {_fmt(q.fcf_margin_pct)}%",
        f"- FCF CAGR (3Y): {_fmt(q.fcf_cagr_3y)}%",
        f"- Interest Coverage: {_fmt(q.interest_coverage)}x",
        f"- Net Debt / EBITDA: {_fmt(q.net_debt_ebitda)}x",
        f"- ROIC: {_fmt(q.roic_pct)}%",
        f"- OCF / Net Income: {_fmt(q.ocf_to_net_income)}",
        f"- FCF Quality Score: {_fmt(q.fcf_quality_score)} / 100",
        f"- Debt Quality Score: {_fmt(q.debt_quality_score)} / 100",
        "",
        "### ⚠️ Solvency (Risk Gate — ไม่รวมใน Composite Score)\n",
        f"- Solvency Score: {_fmt(q.solvency_score)} / 100",
        f"- D/E Ratio: {_fmt(q.de_ratio_pct)}%",
        f"- Current Ratio: {_fmt(q.current_ratio)}x",
        "",
        "### 💧 Trading Liquidity\n",
        f"- ADTV (Average Daily Trading Value): {_fmt_large(q.adtv_local_currency, currency_label)}",
        "",
    ]

    if q.dcf_result:
        d = q.dcf_result
        lines.extend([
            "### 🎯 DCF Target Price & Fair Value Engine\n",
            f"- **Real WACC:** {d.wacc_pct}% (Cost of Equity Ke: {d.cost_of_equity_pct}%, Cost of Debt Kd: {d.cost_of_debt_pct}%)",
            f"- **Macro Parameters:** Risk-Free Rate: {d.risk_free_rate_pct}%, ERP: {d.erp_pct}%",
            f"- **Observable References:** {', '.join(d.observable_refs) if d.observable_refs else 'None (Fallback)'}",
            f"- **Valuation Verdict:** `{d.valuation_verdict.upper()}`",
            "",
            "| Scenario | Target Price | Upside % | Margin of Safety % |",
            "|---|---|---|---|",
            f"| **Bull Case** | ${d.scenarios['bull'].target_price} | {d.scenarios['bull'].upside_pct}% | {d.scenarios['bull'].margin_of_safety_pct}% |",
            f"| **Base Case** | ${d.scenarios['base'].target_price} | {d.scenarios['base'].upside_pct}% | {d.scenarios['base'].margin_of_safety_pct}% |",
            f"| **Bear Case** | ${d.scenarios['bear'].target_price} | {d.scenarios['bear'].upside_pct}% | {d.scenarios['bear'].margin_of_safety_pct}% |",
            "",
        ])

    if q.smart_money_flags:
        sm = q.smart_money_flags
        lines.extend([
            "### 🕵️ Smart Money & Ownership Signals\n",
            f"- Insider Signal: `{sm.insider_signal.upper()}` (Buys: {sm.insider_buy_count_90d}, Sells: {sm.insider_sell_count_90d})",
            f"- Institutional Ownership: {_fmt(sm.institutional_ownership_pct)}%",
            f"- Insider Ownership: {_fmt(sm.insider_ownership_pct)}%",
            f"- Short Interest: {_fmt(sm.short_interest_pct)}% (Short Squeeze Risk: {sm.short_squeeze_risk})",
            f"- Overall Smart Money Flag: `{sm.overall_smart_money_flag.upper()}`",
            "",
        ])

    lines.extend([
        "### 🏢 Peer/Sector Comparison (Contextual — ไม่รวมใน Composite Score)\n",
        f"- Sector: {_fmt(q.peer_sector)}",
        f"- Peer Count: {_fmt(q.peer_count)}",
        f"- P/E vs Peer Average: {_fmt(q.pe_vs_peer_avg_pct)}% (บวก=แพงกว่ากลุ่ม, ลบ=ถูกกว่ากลุ่ม)",
        f"- Peer Relative Score: {_fmt(q.peer_relative_score)} / 100",
        "",
        "### 📅 Historical Price Context (Contextual — ไม่รวมใน Composite Score)\n",
        f"- Price Percentile (5Y): {_fmt(q.price_percentile_5y)}% — ⚠️ เป็น Percentile ของ**ราคา** ไม่ใช่ Valuation Multiple (P/E)",
        f"- Price Z-score (5Y): {_fmt(q.price_zscore_5y)}",
        "",
        "### 🎯 Earnings Momentum (Contextual — ไม่รวมใน Composite Score)\n",
        f"- EPS Revisions (Net, 30 วัน): {_fmt(q.eps_revision_net_30d)}",
        f"- EPS Estimate Change (30 วัน): {_fmt(q.eps_estimate_change_30d_pct)}%",
        f"- Earnings Momentum Score: {_fmt(q.earnings_momentum_score)} / 100",
        "",
    ])

    if q.data_quality_flags:
        lines.append("### ⚠️ Data Quality Flags\n")
        for flag in q.data_quality_flags:
            lines.append(_translate_flag(flag))
        lines.append("")

    lines.append("## 📰 Sentiment & Narrative Context\n")

    if s.key_themes:
        lines.append("**ธีมสำคัญ:** " + ", ".join(s.key_themes))
        lines.append("")
    if s.tail_risks:
        lines.append("**ความเสี่ยงแฝง (Tail Risks):**")
        for risk in s.tail_risks:
            lines.append(f"- {risk}")
        lines.append("")
    lines.append(f"> {s.sources_summary}\n")

    lines.extend([
        "## 📝 บทวิเคราะห์ (Narrative)\n",
        output.narrative_analysis,
        "",
        "## 🎯 Base Case Summary\n",
        output.base_case_summary,
        "",
        "## Related\n",
        f"- [[{output.ticker}]]",
        "",
        "## หมายเหตุ\n",
        "> ตัวเลข Quant Signals ทั้งหมดคำนวณแบบ Deterministic จาก Yahoo Finance — LLM ไม่มีส่วนในการคำนวณตัวเลข",
        "> ใช้ประกอบการวิเคราะห์เท่านั้น ไม่ใช่คำแนะนำการลงทุน",
        "",
    ])

    return "\n".join(lines)

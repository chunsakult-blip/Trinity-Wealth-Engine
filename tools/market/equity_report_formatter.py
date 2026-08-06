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
        "### ⚠️ Solvency (Risk Gate — ไม่รวมใน Composite Score)\n",
        f"- Solvency Score: {_fmt(q.solvency_score)} / 100",
        f"- D/E Ratio: {_fmt(q.de_ratio_pct)}%",
        f"- Current Ratio: {_fmt(q.current_ratio)}x",
        "",
        "### 💧 Trading Liquidity\n",
        f"- ADTV (Average Daily Trading Value): {_fmt_large(q.adtv_local_currency, currency_label)}",
        "",
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
    ]

    if q.data_quality_flags:
        lines.append("> ⚠️ **Data Quality Flags:** " + ", ".join(q.data_quality_flags))
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

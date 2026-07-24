"""Tools สำหรับสร้างและบริหารจัดการ Evidence Bundle ตาม Evidence Contract"""
from datetime import datetime
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from schemas.briefing_book_schemas import (
    BriefingEvidenceBundle,
    EvidenceItem,
    FinancialAutopsySnapshotRef,
    MacroAutopsySnapshot,
    SourceRecord,
)
from schemas.youtube_pitch_schemas import YouTubeContentPitchItem
from schemas.market_data_schemas import MacroObservation


def build_macro_snapshot(observations: List[MacroObservation], mode: str) -> MacroAutopsySnapshot:
    """สร้าง MacroAutopsySnapshot พร้อมประเมินความครบถ้วนของข้อมูล"""
    unavailable = []
    if mode in {"macro", "mixed"}:
        categories = {obs.category for obs in observations}
        if "inflation" not in categories:
            unavailable.append("Missing required macro category: inflation")
        if "rates" not in categories:
            unavailable.append("Missing required macro category: rates")
        if "energy" not in categories:
            unavailable.append("Missing required macro category: energy")

    return MacroAutopsySnapshot(
        observations=observations,
        is_complete=len(unavailable) == 0,
        unavailable_reasons=unavailable,
    )


def _get_independence_key(publisher: str, host: str) -> str:
    pub_clean = (publisher or "").casefold().replace(" ", "")
    host_clean = (host or "").casefold().replace("www.", "")

    # A placeholder publisher carries no ownership information.  Grouping every
    # such source together hides independent domains and makes source diversity
    # scoring meaningless.
    if pub_clean in {"", "unverified", "unknown", "ไม่ยืนยัน", "ไม่ระบุ"}:
        return f"{host_clean or 'unknown_host'}_group"

    if "finnomena" in pub_clean or "finnomena" in host_clean:
        return "finnomena_group"
    if "pi securities" in pub_clean or "pisecurities" in pub_clean:
        return "pi_securities_group"
    if "reuters" in pub_clean or "reuters" in host_clean:
        return "reuters_group"
    if "bloomberg" in pub_clean or "bloomberg" in host_clean:
        return "bloomberg_group"
    if "barron" in pub_clean:
        return "barrons_group"
    if "investing" in pub_clean or "investing.com" in host_clean:
        return "investing_com_group"
    if "prachachat" in pub_clean or "prachachat" in host_clean:
        return "prachachat_group"

    return f"{pub_clean or host_clean}_group"


def _is_placeholder_publisher(value: Any) -> bool:
    clean = str(value or "").strip().casefold().replace(" ", "")
    return clean in {"", "unverified", "unknown", "ไม่ยืนยัน", "ไม่ระบุ"}


def _metric_name_from_line(line: str) -> Optional[str]:
    """Extract a stable label from bullet-style key metrics without guessing values."""
    clean = line.strip().lstrip("-• ")
    if not clean or clean.startswith(("#", ">", "http://", "https://")):
        return None
    label = re.split(r"[:：]", clean, maxsplit=1)[0].strip()
    return label[:80] or None


def _numeric_value_from_line(line: str) -> Optional[float]:
    match = re.search(r"(?<![A-Za-z])(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)", line)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _first_link(source: Dict[str, Any]) -> str:
    links = source.get("links")
    if isinstance(links, list) and links:
        return str(links[0] or "")
    return str(source.get("link") or "")


def _normalise_verification_status(value: Any) -> str:
    """Verification must be supplied by the ingestion layer, never inferred."""
    normalised = str(value or "").strip().lower()
    return normalised if normalised in {"verified", "partial", "unverified"} else "unverified"


def _classify_source(source: Dict[str, Any], host: str) -> str:
    layer = str(source.get("source_layer") or "")
    if layer == "layer2_youtube":
        return "creator_commentary"
    if "reuters" in host or "bloomberg" in host:
        return "wire_service"
    if layer in {"layer1_store", "layer1", "layer2_notes"}:
        return "analysis"
    return "unknown"


def build_briefing_evidence(
    pitch: YouTubeContentPitchItem,
    matched_sources: List[Dict[str, Any]],
    macro_snapshot: Optional[MacroAutopsySnapshot] = None,
    financial_snapshots: Optional[List[FinancialAutopsySnapshotRef]] = None,
) -> BriefingEvidenceBundle:
    """แปลง Pitch และ Candidates เป็น BriefingEvidenceBundle โดยกำหนด Stable IDs (S01, S02, E01, E02)"""
    source_records: List[SourceRecord] = []
    evidence_items: List[EvidenceItem] = []

    seen_urls = set()
    candidates_by_source_id: Dict[str, Dict[str, Any]] = {}
    s_idx = 1
    e_idx = 1

    # 1. แปลง Candidates เป็น SourceRecord (S01, S02...)
    for src in matched_sources:
        link = str(src.get("canonical_url") or _first_link(src) or "")
        if link and link in seen_urls:
            continue
        if link:
            seen_urls.add(link)

        sid = f"S{s_idx:02d}"
        s_idx += 1

        orig_title = src.get("original_title") or src.get("canonical_title") or src.get("title") or "ไม่พบชื่ออ้างอิง"
        publisher = src.get("publisher") or src.get("channel") or src.get("source") or "ไม่ยืนยัน"
        host = urlsplit(link).netloc.replace("www.", "") if link else "unknown_host"
        canonical_publisher = src.get("canonical_publisher")
        if canonical_publisher:
            publisher = canonical_publisher
        if isinstance(publisher, (list, tuple, set)):
            publisher = next((str(item).strip() for item in publisher if str(item).strip()), "Unverified publisher")
        if not src.get("original_title") and not src.get("title"):
            # A synthesized/canonical label is editorial metadata, not provenance.
            orig_title = "Unverified source title"
        pub_at = src.get("canonical_published_at") or src.get("published_at")
        ing_at = src.get("ingested_at") or datetime.now().isoformat()
        ver_status = _normalise_verification_status(src.get("verification_status"))

        stype = _classify_source(src, host)

        ind_key = _get_independence_key(publisher, host)

        source_records.append(
            SourceRecord(
                source_id=sid,
                original_title=orig_title,
                publisher=publisher,
                host=host,
                published_at=pub_at if (pub_at and pub_at != "None") else None,
                ingested_at=str(ing_at),
                url=link or "N/A",
                source_type=stype,  # type: ignore
                independence_key=ind_key,
                verification_status=ver_status,  # type: ignore
            )
        )
        candidates_by_source_id[sid] = src

    # 2. สร้าง EvidenceItems จาก Macro Snapshot (E01, E02...)
    if macro_snapshot and macro_snapshot.observations:
        for obs in macro_snapshot.observations:
            # Keep stale observations in the snapshot for diagnostics, but do
            # not promote them into evidence that an LLM may cite as current.
            if obs.is_stale:
                continue
            eid = f"E{e_idx:02d}"
            e_idx += 1

            ret_str = ""
            if obs.returns:
                ret_parts = [f"{k}:{v:+.2f}%" for k, v in obs.returns.items() if v is not None]
                if ret_parts:
                    ret_str = f" ({', '.join(ret_parts)})"

            claim_text = f"ตัวเลขเศรษฐกิจ {obs.label} ({obs.series_id}) ล่าสุดคือ {obs.value:,.2f} {obs.unit} ณ วันที่ {obs.observed_at} (Provider: {obs.provider}){ret_str}"

            # สร้าง Macro Provider SourceRecord ถ้ายังไม่มี
            macro_sid = f"S_MACRO_{obs.series_id}"
            if not any(s.source_id == macro_sid for s in source_records):
                source_records.append(
                    SourceRecord(
                        source_id=macro_sid,
                        original_title=f"Macro Market Series {obs.series_id} ({obs.label})",
                        publisher=obs.provider,
                        host=urlsplit(obs.source_url).netloc.replace("www.", "") if obs.source_url else obs.provider.lower(),
                        published_at=obs.observed_at,
                        ingested_at=datetime.now().isoformat(),
                        url=obs.source_url or "N/A",
                        source_type="data_provider",
                        independence_key=f"macro_provider_{obs.provider.lower()}",
                        verification_status="verified" if obs.confidence == "high" and obs.source_url else "partial",
                    )
                )

            evidence_items.append(
                EvidenceItem(
                    evidence_id=eid,
                    claim=claim_text,
                    classification="verified_fact" if obs.confidence == "high" and obs.source_url else "source_reported_fact",
                    value=obs.value,
                    unit=obs.unit,
                    observed_at=obs.observed_at,
                    reported_at=obs.observed_at,
                    time_semantics="observed",
                    source_excerpt=f"{obs.provider} series {obs.series_id}, observed {obs.observed_at}",
                    source_ids=[macro_sid],
                    confidence=obs.confidence,
                    caveat="สกัดจากข้อมูลตลาด Real-time Quantitative Series",
                    metric_name=obs.series_id or obs.label,
                    period_type="daily_close",
                )
            )

    # 3. สกัด EvidenceItems จาก Candidate Summary/Key Metrics
    # Turn provider financial periods into citable numeric evidence.  Without
    # this bridge, a stock draft would receive real FCF/debt data but could not
    # cite or pass the numeric-grounding gate.
    for snapshot in financial_snapshots or []:
        if snapshot.status != "success" or not snapshot.periods:
            continue
        safe_symbol = re.sub(r"[^A-Z0-9]", "_", snapshot.symbol.upper())
        financial_sid = f"S_FIN_{safe_symbol}"
        if not any(source.source_id == financial_sid for source in source_records):
            source_records.append(
                SourceRecord(
                    source_id=financial_sid,
                    original_title=f"Financial statements for {snapshot.symbol}",
                    publisher=snapshot.source or "Yahoo Finance",
                    host="finance.yahoo.com",
                    published_at=None,
                    ingested_at=datetime.now().isoformat(),
                    url="N/A",
                    source_type="data_provider",
                    independence_key="yahoo_finance_group",
                    verification_status="partial",
                )
            )
        for period in snapshot.periods:
            metrics = {
                "Free cash flow": period.free_cash_flow,
                "Revenue": period.total_revenue,
                "Net income": period.net_income,
                "Total debt": period.total_debt,
                "Payout ratio": period.payout_ratio_pct,
            }
            for metric_name, value in metrics.items():
                if value is None:
                    continue
                eid = f"E{e_idx:02d}"
                e_idx += 1
                unit = "%" if metric_name == "Payout ratio" else (snapshot.currency or "reported currency")
                evidence_items.append(
                    EvidenceItem(
                        evidence_id=eid,
                        claim=f"{snapshot.symbol} {metric_name} for {period.fiscal_period_end}: {value:,.2f} {unit}",
                        classification="source_reported_fact",
                        value=value,
                        unit=unit,
                        observed_at=period.fiscal_period_end,
                        reported_at=period.fiscal_period_end,
                        time_semantics="fiscal_period",
                        source_excerpt=f"Provider financial statement period ending {period.fiscal_period_end}",
                        source_ids=[financial_sid],
                        confidence="medium",
                        caveat="Provider financial-statement snapshot; verify against the issuer filing for decisions.",
                        metric_name=f"{snapshot.symbol}:{metric_name}",
                        period_type="fiscal_period",
                    )
                )

    for s_rec in source_records:
        if s_rec.source_id.startswith("S_MACRO_"):
            continue

        matched_cand = candidates_by_source_id.get(s_rec.source_id)
        if not matched_cand:
            continue

        summary = matched_cand.get("comprehensive_summary") or matched_cand.get("summary") or ""
        key_metrics = matched_cand.get("key_metrics") or ""

        # สกัดตัวเลขจาก key_metrics หรือ summary
        metric_lines = [
            line.strip() for line in str(key_metrics).splitlines()
            if _metric_name_from_line(line) is not None
        ]
        for metric_line in metric_lines[:8]:
            metric_name = _metric_name_from_line(metric_line)
            if metric_name is None:
                continue
            eid = f"E{e_idx:02d}"
            e_idx += 1
            evidence_items.append(
                EvidenceItem(
                    evidence_id=eid,
                    claim=f"{s_rec.original_title}: {metric_line[:240]}",
                    classification="source_reported_fact",
                    value=_numeric_value_from_line(metric_line),
                    # A publication date tells us when a source reported the
                    # number, not necessarily when the market observation was
                    # made.  Keep those semantics separate so a later quality
                    # review cannot treat two article timestamps as price fixes.
                    observed_at=None,
                    reported_at=s_rec.published_at,
                    time_semantics="reported" if s_rec.published_at else "unknown",
                    source_excerpt=metric_line[:240],
                    source_ids=[s_rec.source_id],
                    confidence="medium" if s_rec.verification_status != "unverified" else "low",
                    caveat="Source-reported metric; confirm timestamp and original publisher before treating as fact.",
                    metric_name=metric_name,
                    period_type="instant",
                )
            )

        if key_metrics and not metric_lines:
            eid = f"E{e_idx:02d}"
            e_idx += 1
            evidence_items.append(
                EvidenceItem(
                    evidence_id=eid,
                    claim=f"ตัวเลขสำคัญจาก {s_rec.original_title}: {key_metrics}",
                    classification="source_reported_fact",
                    source_ids=[s_rec.source_id],
                    confidence="medium",
                    caveat="รายงานโดยสำนักข่าว/ช่อง YouTube"
                )
            )

        # สกัดประเด็นหลักเป็น evidence
        lines = [
            line.strip("- ") for line in summary.splitlines()
            if line.strip()
            and not line.lstrip().startswith(("[", "#", ">", "---", "http://", "https://"))
            and "source_url:" not in line.casefold()
            and len(line.strip()) > 15
        ]
        for line in lines[:2]:
            eid = f"E{e_idx:02d}"
            e_idx += 1
            classification = "source_reported_fact"
            if "คาด" in line or "ประมาณ" in line or "consensus" in line.lower():
                # A single source mentioning an expectation is not a consensus.
                classification = "source_reported_fact"
            elif "สมมติฐาน" in line or "อาจ" in line:
                classification = "hypothesis"

            evidence_items.append(
                EvidenceItem(
                    evidence_id=eid,
                    claim=f"{s_rec.publisher} รายงาน: {line[:180]}",
                    classification=classification,  # type: ignore
                    source_ids=[s_rec.source_id],
                    confidence="medium" if s_rec.verification_status == "verified" else "low",
                    caveat=f"มาจาก {s_rec.source_type}"
                )
            )

    return BriefingEvidenceBundle(
        pitch_id=pitch.pitch_id,
        investigation_mode=pitch.investigation_mode,
        sources=source_records,
        evidence_items=evidence_items,
        macro_snapshot=macro_snapshot,
        financial_snapshots=financial_snapshots or [],
    )

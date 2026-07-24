"""Renderer for Briefing Book to transform Draft into Markdown."""
import re
from typing import List

from schemas.briefing_book_schemas import (
    InvestigativeBriefingBookDraft,
    BriefingEvidenceBundle,
    RenderedBriefing,
    RenderedVisualMarker,
)


def _collect_ids(text: str, prefix: str) -> set:
    if not text:
        return set()
    return set(re.findall(r"\[(" + prefix + r"\d+)\]", str(text)))


def render_briefing_book(
    draft: InvestigativeBriefingBookDraft,
    bundle: BriefingEvidenceBundle
) -> RenderedBriefing:
    lines = [f"# {draft.title}"]
    lines.append(draft.executive_summary)
    
    section_names = ["Main Title (H1)", "Executive Summary"]
    
    def strip_markers(text):
        if not text: return ""
        return re.sub(r'\[VISUAL_EVIDENCE[^\]]*\]', '', str(text))
        
    acts = [
        ("Act I", strip_markers(draft.act1_script)),
        ("Act II", strip_markers(draft.act2_script)),
        ("Act III", strip_markers(draft.act3_script))
    ]
    
    directives_by_act = {}
    visual_markers = []
    
    for d in draft.visual_directives:
        act = getattr(d, "act", "")
        directives_by_act.setdefault(act, []).append(d)
        
    for act_name, script in acts:
        lines.append(f"## {act_name}")
        section_names.append(act_name)
        if script.strip():
            lines.append(script.strip())
        
        for d in directives_by_act.get(act_name, []):
            ev_ids = getattr(d, "evidence_ids", [])
            vid = getattr(d, 'visual_id', '')
            ev_str = ",".join(ev_ids) if ev_ids else "UNKNOWN"
            lines.append(f"[VISUAL_EVIDENCE id={vid} evidence={ev_str}]")
            visual_markers.append(RenderedVisualMarker(id=vid, evidence_ids=ev_ids, act=act_name))
            
    if draft.causality_scenarios:
        lines.append("## Causality Scenarios")
        section_names.append("Causality Scenarios")
        for sc in draft.causality_scenarios:
            lines.append(f"### {sc.name}")
            lines.append(sc.description)
            lines.append(f"Time Horizon: {sc.time_horizon}")

    if draft.asset_impacts:
        lines.append("## Asset Impacts")
        section_names.append("Asset Impacts")
        for imp in draft.asset_impacts:
            lines.append(f"### {imp.symbol_or_name}")
            lines.append(f"Direction: {imp.impact_type}")
            lines.append(f"Invalidation: {', '.join(imp.invalidation_conditions)}")

    if draft.bull_case or draft.bear_case:
        lines.append("## Bull & Bear Cases")
        section_names.append("Bull & Bear Cases")
        lines.append(f"Bull: {draft.bull_case}")
        lines.append(f"Bear: {draft.bear_case}")

    if draft.notebooklm_prompts:
        lines.append("## NotebookLM Prompts")
        section_names.append("NotebookLM Prompts")
        for p in draft.notebooklm_prompts:
            ptype = getattr(p, "prompt_type", "GENERAL")
            q = getattr(p, "question_or_prompt", str(p))
            out = getattr(p, "expected_output_format", "")
            lines.append(f"- [{ptype}] {q}\n  *Output Format: {out}*")

    lines.append("## Evidence Ledger")
    section_names.append("Evidence Ledger")
    if bundle.sources:
        lines.append("### Sources")
        for s in bundle.sources:
            lines.append(f"- **[{s.source_id}]** {s.original_title} ({s.publisher}, {s.published_at or 'unverified'})")
    if bundle.evidence_items:
        lines.append("### Facts")
        for e in bundle.evidence_items:
            lines.append(f"- **[{e.evidence_id}]** {e.claim} (Sources: {', '.join(e.source_ids)})")

    content = "\n\n".join(lines)
    
    cited_evidence_ids = _collect_ids(content, "E")
    cited_source_ids = _collect_ids(content, "S")
    
    return RenderedBriefing(
        content=content,
        section_names=section_names,
        visual_markers=visual_markers,
        cited_evidence_ids=cited_evidence_ids,
        cited_source_ids=cited_source_ids,
    )

def render_briefing_book_markdown(draft: InvestigativeBriefingBookDraft, bundle: BriefingEvidenceBundle) -> str:
    # Forward-compatibility wrapper for any remaining legacy callers
    return render_briefing_book(draft, bundle).content

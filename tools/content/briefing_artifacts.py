import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Union

from filelock import FileLock
from core.logger import get_logger

logger = get_logger(__name__)

from schemas.briefing_book_schemas import PublishableBriefingResult, UnverifiedBriefingDraftResult, SavedBriefingArtifact
from tools.archivist.core import _sanitize_filename
from tools._atomic_io import _stage_text

def save_briefing_artifact(
    synthesis: Union[PublishableBriefingResult, UnverifiedBriefingDraftResult],
    title: str,
    *,
    vault_root: Path,
    date_str: Optional[str] = None,
) -> SavedBriefingArtifact:
    """
    Save content and quality report together atomically, then invoke indexer (if publishable).
    Uses vault_override for isolation testing so tests don't pollute the production Vault.
    """
    if not isinstance(synthesis, (PublishableBriefingResult, UnverifiedBriefingDraftResult)):
        raise TypeError("Input must be PublishableBriefingResult or UnverifiedBriefingDraftResult")

    is_draft = isinstance(synthesis, UnverifiedBriefingDraftResult)
    content = synthesis.content
    report = synthesis.quality_report

    if not is_draft:
        if getattr(synthesis, "artifact_status", None) != "publishable":
            raise ValueError("Publishable result must have artifact_status='publishable'")
        if not report.publishable:
            raise ValueError("Publishable result must have publishable=True in report")
        if report.status not in ("pass", "degraded"):
            raise ValueError(f"Publishable result must have status 'pass' or 'degraded', got {report.status}")
        if hasattr(report, "hard_blockers") and report.hard_blockers:
            raise ValueError("Publishable result cannot have hard blockers")
    else:
        if getattr(synthesis, "artifact_status", None) != "unverified_draft":
            raise ValueError("Unverified draft must have artifact_status='unverified_draft'")
        if getattr(synthesis, "trust_tier", None) != "unverified":
            raise ValueError("Unverified draft must have trust_tier='unverified'")
        if not getattr(synthesis, "override_audit", None):
            raise ValueError("Unverified draft must have override_audit")
        if not synthesis.override_audit.token_hash:
            raise ValueError("Unverified draft must have valid token_hash")
        
        for issue in report.issues:
            if issue.severity in ("blocker", "cap") and not getattr(issue, "bypassable", False):
                raise ValueError(f"Unverified draft contains non-bypassable issue: {issue.code}")

    pitch_id = "unknown"
    if getattr(synthesis, "evidence_bundle", None) and getattr(synthesis.evidence_bundle, "pitch_id", None):
        pitch_id = synthesis.evidence_bundle.pitch_id

    target_vault = vault_root
    target_dir = target_vault / "30_Knowledge_Base" / "NotebookLM_Sources"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    lock = FileLock(target_dir / ".lock", timeout=30)
    with lock:
        d_str = date_str or datetime.now().strftime("%Y-%m-%d")
        safe_title = _sanitize_filename(title.strip()[:80])
        
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        revision = getattr(synthesis, "approval_revision", getattr(report, "approval_revision", 1))
        
        suffix_part = "DRAFT" if is_draft else pitch_id
        status_tag = "unverified" if is_draft else "verified"
        
        # Idempotency: Use revision and hash in filename
        file_path = target_dir / f"{d_str}_{safe_title}_{suffix_part}_rev{revision}_{content_hash[:8]}_{status_tag}.md"
        
        quality_path = file_path.with_suffix(".quality.json")
        
        # If the file already exists, we can consider this an idempotent retry and skip writing if we want.
        # But writing it again atomically is also idempotent.
    
        report_data = {}
        if report:
            if hasattr(report, "model_dump"):
                report_data = report.model_dump(mode="json")
            elif hasattr(report, "dict"):
                report_data = report.dict()
            elif isinstance(report, dict):
                report_data = report.copy()
        
        report_data["content_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        if is_draft:
            report_data["is_unverified_draft"] = True
            
        if hasattr(synthesis, "override_audit") and synthesis.override_audit:
            if hasattr(synthesis.override_audit, "model_dump"):
                report_data["override_audit"] = synthesis.override_audit.model_dump(mode="json")
            elif hasattr(synthesis.override_audit, "dict"):
                report_data["override_audit"] = synthesis.override_audit.dict()
            else:
                report_data["override_audit"] = synthesis.override_audit
    
        content_temp = _stage_text(file_path, content)
        quality_temp = _stage_text(quality_path, json.dumps(report_data, ensure_ascii=False, indent=2))
    
        try:
            os.replace(quality_temp, quality_path)
            os.replace(content_temp, file_path)
        except Exception:
            content_temp.unlink(missing_ok=True)
            quality_temp.unlink(missing_ok=True)
            if not file_path.exists():
                quality_path.unlink(missing_ok=True)
            raise

    # Index into the provided vault
    index_status: Literal["indexed", "pending", "failed"] = "pending"
    index_error = None
    if not is_draft:
        try:
            from tools.archivist.indexer import _index_upsert, flush_index_if_dirty
            _index_upsert(file_path, vault_root=vault_root)
            flush_index_if_dirty(vault_root=vault_root)
            logger.info("Saved NotebookLM briefing to %s", file_path)
            index_status = "indexed"
        except Exception as e:
            logger.error("Failed to index artifact: %s", str(e))
            index_status = "failed"
            index_error = str(e)
    else:
        status_msg = "UNVERIFIED"
        logger.warning("Saved %s NotebookLM briefing/draft to %s", status_msg, file_path)
        
    return SavedBriefingArtifact(
        path=file_path,
        quality_path=quality_path,
        index_status=index_status,
        index_error=index_error,
    )

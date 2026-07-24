import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from filelock import FileLock
from core.logger import get_logger

logger = get_logger(__name__)

from schemas.briefing_book_schemas import BriefingSynthesisResult, UnverifiedBriefingDraftResult
from tools.archivist.core import VAULT_PATH, _sanitize_filename
from tools._atomic_io import _stage_text

def save_briefing_artifact(
    synthesis: Union[BriefingSynthesisResult, UnverifiedBriefingDraftResult],
    title: str,
    date_str: Optional[str] = None,
    vault_override: Optional[Path] = None,
) -> str:
    """
    Save content and quality report together atomically, then invoke indexer (if publishable).
    Uses vault_override for isolation testing so tests don't pollute the production Vault.
    """
    is_draft = isinstance(synthesis, UnverifiedBriefingDraftResult)
    content = synthesis.content
    report = getattr(synthesis, "quality_report", None)
    
    pitch_id = "unknown"
    if hasattr(synthesis, "evidence_bundle") and hasattr(synthesis.evidence_bundle, "pitch_id"):
        pitch_id = getattr(synthesis.evidence_bundle, "pitch_id", "unknown")

    target_vault = vault_override if vault_override else Path(VAULT_PATH)
    target_dir_name = "NotebookLM_Drafts" if is_draft else "NotebookLM"
    target_dir = target_vault / "00_Inbox" / target_dir_name
    target_dir.mkdir(parents=True, exist_ok=True)
    
    lock = FileLock(target_dir / ".lock", timeout=30)
    with lock:
        d_str = date_str or datetime.now().strftime("%Y-%m-%d")
        safe_title = _sanitize_filename(title.strip()[:80])
        
        suffix_part = "DRAFT" if is_draft else pitch_id
        file_path = target_dir / f"{d_str}_{safe_title}_{suffix_part}.md"
        
        counter = 2
        while file_path.exists():
            file_path = target_dir / f"{d_str}_{safe_title}_{suffix_part}_{counter}.md"
            counter += 1
                
        quality_path = file_path.with_suffix(".quality.json")
    
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

    # Only index into production vault if no override is provided.
    if not is_draft and vault_override is None:
        from tools.archivist.indexer import _index_upsert, flush_index_if_dirty
        _index_upsert(file_path, vault_root=Path(VAULT_PATH))
        flush_index_if_dirty(vault_root=Path(VAULT_PATH))
        logger.info("Saved NotebookLM briefing to %s", file_path)
    else:
        status_msg = "UNVERIFIED" if is_draft else "ISOLATED"
        logger.warning("Saved %s NotebookLM briefing/draft to %s", status_msg, file_path)
        
    return str(file_path.resolve())

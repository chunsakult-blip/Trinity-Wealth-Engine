import glob
import json
import logging
import os
import re
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from api.auth import require_session
from api.schemas import (
    EquitySummaryDTO, EquityDetailDTO, EquitySentimentContextDTO,
    EquityNewsDTO, EquityNewsItemDTO, EquityNoteItemDTO, EquityNotesDTO, EquityNoteContentDTO
)
from core.nlp_utils import calculate_freshness
from schemas.macro_schemas import ThemeCategory
from schemas.micro_quant_schemas import MicroQuantOutput
from tools.archivist.core import VAULT_PATH
from tools.archivist.parser import parse_company_news_items, extract_yaml_frontmatter_value
from tools.portfolio.journal import _JOURNAL_BLOCK_RE

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/equity",
    tags=["equity"],
    dependencies=[Depends(require_session)],
)

def _validate_ticker(ticker: str) -> str:
    ticker = ticker.upper()
    if not re.match(r"^[A-Z0-9.\-_]+$", ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker format")
    if ".." in ticker or "/" in ticker or "\\" in ticker:
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return ticker

def _validate_schema(data: dict, expected_ticker: str) -> MicroQuantOutput | None:
    """Deep validation of required fields for Equity Sidecar JSON using Pydantic."""
    try:
        model = MicroQuantOutput.model_validate(data)
        
        # Date formats validation
        datetime.strptime(model.analysis_date, "%Y-%m-%d")
        datetime.fromisoformat(model.quant_signals.evaluated_at.replace("Z", "+00:00"))
        datetime.fromisoformat(model.sentiment_context.evaluated_at.replace("Z", "+00:00"))
        
        if expected_ticker.upper() != model.ticker.upper():
            return None
        if model.ticker.upper() != model.quant_signals.ticker.upper():
            return None
            
        return model
    except (ValidationError, ValueError, TypeError):
        return None

def _get_equity_files(ticker: str = None) -> list[Path]:
    """Get JSON sidecar files, optionally filtered by ticker."""
    pattern = "30_Knowledge_Base/Stocks/*/* Equity Analysis *.json"
    if ticker:
        pattern = f"30_Knowledge_Base/Stocks/{ticker}/{ticker} Equity Analysis *.json"
    
    # glob.glob on Vault
    files = list(VAULT_PATH.glob(pattern))
    return files

def _extract_date_key(file_path: Path) -> tuple[str, str]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            ev = data.get("quant_signals", {}).get("evaluated_at", "")
            if ev:
                return (ev, file_path.name)
    except Exception:
        pass
        
    try:
        date_str = file_path.stem.split(" ")[-1]
        return (date_str, file_path.name)
    except Exception:
        return ("", file_path.name)

def _get_latest_sidecar_for_ticker(files: list[Path], expected_ticker: str, strict: bool = False) -> tuple[MicroQuantOutput, Path] | None:
    if not files:
        return None
        
    if strict:
        files_sorted = sorted(files, key=lambda f: _extract_date_key(f), reverse=True)
        latest_file = files_sorted[0]
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            model = _validate_schema(data, expected_ticker)
            if model:
                return (model, latest_file)
            else:
                log.warning(f"Strict mode: latest file is invalid {latest_file}")
                return None
        except Exception:
            return None
    else:
        valid_files = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as file_obj:
                    data = json.load(file_obj)
                model = _validate_schema(data, expected_ticker)
                if model:
                    valid_files.append((model, f))
                else:
                    log.warning(f"Malformed or invalid schema in equity sidecar: {f}")
            except Exception:
                pass
                
        if not valid_files:
            return None
            
        valid_files.sort(key=lambda x: (x[0].quant_signals.evaluated_at, x[1].name), reverse=True)
        return valid_files[0]

@router.get("/latest", response_model=List[EquitySummaryDTO])
def get_latest_equities():
    files = _get_equity_files()
    
    # Group by ticker
    ticker_files = {}
    for f in files:
        # Ticker is the folder name containing the file
        ticker = f.parent.name
        if ticker not in ticker_files:
            ticker_files[ticker] = []
        ticker_files[ticker].append(f)
            
    results = []
    for ticker, paths in ticker_files.items():
        latest = _get_latest_sidecar_for_ticker(paths, ticker, strict=False)
        if latest:
            model, file_path = latest
            rel_path = str(file_path.relative_to(VAULT_PATH)).replace("\\", "/")
            source_md = rel_path.replace(".json", ".md")
            
            summary = EquitySummaryDTO(
                ticker=model.ticker,
                market=model.market,
                company_name=model.quant_signals.company_name,
                analysis_date=model.analysis_date,
                evaluated_at=model.quant_signals.evaluated_at,
                market_sentiment=model.sentiment_context.market_sentiment,
                composite_score=model.quant_signals.composite_score,
                data_quality_flags=getattr(model.quant_signals, "data_quality_flags", []),
                source_file=source_md,
                sidecar_file=rel_path
            )
            results.append(summary)
            
    results.sort(key=lambda x: (x.evaluated_at, x.ticker), reverse=True)
    return results


def _is_agent_generated(file_path: Path, content: str) -> bool:
    name = file_path.name
    if file_path.suffix == ".json":
        return True
    
    # 1. Check Frontmatter signals (Case-insensitive)
    val_entity = (extract_yaml_frontmatter_value(content, "entity_type") or "").lower().replace(" ", "_")
    val_agent = extract_yaml_frontmatter_value(content, "generated_by")
    if val_entity in ("company_news", "equity_analysis") or val_agent:
        return True

    # 2. Check filename pattern (Supports space and underscore: Latest_News, Latest News, Equity_Analysis, Equity Analysis)
    if re.search(r"(?i)latest[_\s]news|equity[_\s]analysis", name):
        return True

    return False


@router.get("/notes/content", response_model=EquityNoteContentDTO)
def get_equity_note_content(rel_path: str):
    if ".." in rel_path or rel_path.startswith("/") or rel_path.startswith("\\"):
        raise HTTPException(status_code=400, detail="Invalid path format")

    vault_resolved = VAULT_PATH.resolve()
    target_path = (VAULT_PATH / rel_path).resolve()

    # Robust path traversal check using Path.is_relative_to()
    if not target_path.is_relative_to(vault_resolved):
        raise HTTPException(status_code=403, detail="Access denied: Outside vault boundary")
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="Note file not found")
    if target_path.suffix != ".md":
        raise HTTPException(status_code=400, detail="Only markdown files can be read")

    try:
        content = target_path.read_text(encoding="utf-8")
        mtime = datetime.fromtimestamp(target_path.stat().st_mtime, tz=timezone.utc).isoformat()
        return EquityNoteContentDTO(
            title=target_path.stem,
            relative_path=rel_path,
            content=content,
            modified_at=mtime
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read note content: {str(e)}")


@router.get("/{ticker}", response_model=EquityDetailDTO)
def get_equity_detail(ticker: str):
    ticker = _validate_ticker(ticker)
    files = _get_equity_files(ticker)
    
    if not files:
        raise HTTPException(status_code=404, detail="Equity not found")
        
    latest = _get_latest_sidecar_for_ticker(files, ticker, strict=True)
    if not latest:
        # If strict=True and it returns None, it means the latest file was corrupted or mismatched.
        raise HTTPException(status_code=503, detail="Service Unavailable: Data corrupted or ticker mismatch")
        
    model, latest_file = latest
        
    rel_path = str(latest_file.relative_to(VAULT_PATH)).replace("\\", "/")
    source_md = rel_path.replace(".json", ".md")
    
    sentiment_ctx = EquitySentimentContextDTO(
        evaluated_at=model.sentiment_context.evaluated_at,
        market_sentiment=model.sentiment_context.market_sentiment,
        key_themes=model.sentiment_context.key_themes,
        tail_risks=model.sentiment_context.tail_risks,
        sources_summary=model.sentiment_context.sources_summary,
        report_references=model.sentiment_context.report_references
    )
    
    detail = EquityDetailDTO(
        ticker=model.ticker,
        market=model.market,
        company_name=model.quant_signals.company_name,
        analysis_date=model.analysis_date,
        evaluated_at=model.quant_signals.evaluated_at,
        market_sentiment=model.sentiment_context.market_sentiment,
        composite_score=model.quant_signals.composite_score,
        data_quality_flags=getattr(model.quant_signals, "data_quality_flags", []),
        source_file=source_md,
        sidecar_file=rel_path,
        quant_signals=model.quant_signals.model_dump(),
        sentiment_context=sentiment_ctx,
        narrative_analysis=model.narrative_analysis,
        base_case_summary=model.base_case_summary,
        generated_by=model.generated_by
    )
    
    return detail


def _get_equity_news_from_vault(ticker: str) -> EquityNewsDTO | None:
    json_pattern = f"30_Knowledge_Base/Stocks/{ticker}/{ticker}*News*.json"
    json_files = list(VAULT_PATH.glob(json_pattern))

    md_pattern = f"30_Knowledge_Base/Stocks/{ticker}/{ticker}*News*.md"
    md_files = list(VAULT_PATH.glob(md_pattern))

    if not json_files and not md_files:
        return None

    now_utc = datetime.now(timezone.utc)
    raw_data = None

    if json_files:
        json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest_json = json_files[0]
        try:
            with open(latest_json, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception as e:
            log.warning("Failed to read news sidecar JSON %s: %s", latest_json, e)

    if not raw_data and md_files:
        md_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest_md = md_files[0]
        try:
            content = latest_md.read_text(encoding="utf-8")
            raw_data = parse_company_news_items(content)
        except Exception as e:
            log.warning("Failed to fallback parse news MD %s: %s", latest_md, e)

    if not raw_data or not isinstance(raw_data, dict):
        return None

    items_dto = []
    for item in raw_data.get("items", []):
        pub_at_str = item.get("published_at")
        pub_at_dt = None
        if pub_at_str:
            try:
                pub_at_dt = datetime.fromisoformat(pub_at_str.replace("Z", "+00:00"))
                if pub_at_dt.tzinfo is None:
                    pub_at_dt = pub_at_dt.replace(tzinfo=timezone.utc)
            except Exception:
                pub_at_dt = None

        if pub_at_dt:
            age_hours = int((now_utc - pub_at_dt).total_seconds() / 3600)
            freshness_score, freshness_reason = calculate_freshness(age_hours, ThemeCategory.RISK_SENTIMENT)
            is_stale = age_hours > 48
        else:
            age_hours = item.get("age_hours", 9999)
            freshness_reason = item.get("freshness_reason", "Unknown age")
            is_stale = item.get("is_stale", True)

        items_dto.append(
            EquityNewsItemDTO(
                title=item.get("title", ""),
                source=item.get("source", "N/A"),
                link=item.get("link", ""),
                published_at=pub_at_str,
                age_hours=age_hours,
                freshness_reason=freshness_reason,
                is_stale=is_stale,
                sources_count=item.get("sources_count", 1)
            )
        )

    m_val = raw_data.get("market", "US")
    market = "TH" if m_val == "TH" else "US"

    return EquityNewsDTO(
        ticker=raw_data.get("ticker", ticker),
        market=market,
        last_updated=raw_data.get("last_updated"),
        news_date=raw_data.get("date"),
        items=items_dto
    )


@router.get("/{ticker}/news", response_model=EquityNewsDTO)
def get_equity_news(ticker: str):
    ticker = _validate_ticker(ticker)
    news_dto = _get_equity_news_from_vault(ticker)
    if not news_dto:
        raise HTTPException(status_code=404, detail="ยังไม่มีข้อมูลข่าวสำหรับหุ้นตัวนี้ในระบบ")
    return news_dto


_DATE_REGEX = re.compile(r"20\d{2}-\d{2}-\d{2}")

def _extract_note_datetime(filename: str, mtime: float, content: str = "") -> datetime:
    m = _DATE_REGEX.search(filename)
    if m:
        try:
            return datetime.strptime(m.group(0), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            pass
    if content:
        val_date = extract_yaml_frontmatter_value(content, "date")
        if val_date:
            m_fm = _DATE_REGEX.search(str(val_date))
            if m_fm:
                try:
                    return datetime.strptime(m_fm.group(0), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except Exception:
                    pass
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


@router.get("/{ticker}/notes", response_model=EquityNotesDTO)
def get_equity_notes(ticker: str, days: int = 3):
    ticker = _validate_ticker(ticker)
    ticker_upper = ticker.upper()
    vault_name = os.getenv("OBSIDIAN_VAULT_NAME", VAULT_PATH.name)

    now_utc = datetime.now(timezone.utc)
    cutoff_dt = (now_utc - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0) if days > 0 else None

    # Robust regex patterns
    tag_pattern = re.compile(rf"(?i)(?<![A-Za-z0-9_])#{re.escape(ticker_upper)}\b")
    # Matches [[AAPL]], [[AAPL|Apple]], [[AAPL#Section]], [[Stocks/AAPL]]
    wikilink_pattern = re.compile(rf"(?i)\[\[(?:[^\]]+/)?{re.escape(ticker_upper)}(?:[|#][^\]]*)?\]\]")
    frontmatter_pattern = re.compile(rf"(?i)^\s*tickers?:\s*\[?.*?\b{re.escape(ticker_upper)}\b", re.MULTILINE)

    notes: list[EquityNoteItemDTO] = []
    seen_paths = set()

    # Search explicitly in News and YouTube_Summaries folders
    target_dirs = [
        VAULT_PATH / "30_Knowledge_Base" / "News",
        VAULT_PATH / "30_Knowledge_Base" / "YouTube_Summaries",
    ]

    for target_dir in target_dirs:
        if not target_dir.exists():
            continue

        for md_file in target_dir.glob("*.md"):
            rel_path = str(md_file.relative_to(VAULT_PATH)).replace("\\", "/")
            if rel_path in seen_paths:
                continue
            if md_file.name.startswith(".") or md_file.name == "index.md":
                continue

            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                matched_by = None
                if tag_pattern.search(content):
                    matched_by = "tag"
                elif wikilink_pattern.search(content):
                    matched_by = "wikilink"
                elif frontmatter_pattern.search(content):
                    matched_by = "frontmatter"

                if matched_by:
                    seen_paths.add(rel_path)
                    mtime = md_file.stat().st_mtime
                    note_dt = _extract_note_datetime(md_file.name, mtime, content)
                    if cutoff_dt is not None and note_dt < cutoff_dt:
                        continue

                    folder_display = str(md_file.parent.relative_to(VAULT_PATH)).replace("\\", "/")
                    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("---")]
                    snippet = " ".join(lines[:3])[:250]

                    if "YouTube_Summaries" in folder_display:
                        matched_by = "youtube"
                    elif "News" in folder_display:
                        matched_by = "news"

                    notes.append(EquityNoteItemDTO(
                        title=md_file.stem,
                        folder=folder_display,
                        relative_path=rel_path,
                        obsidian_uri=f"obsidian://open?vault={vault_name}&file={rel_path}",
                        snippet=snippet,
                        modified_at=note_dt.isoformat(),
                        matched_by=matched_by
                    ))
            except Exception as e:
                log.warning("Failed to search note file %s: %s", md_file, e)

    notes.sort(key=lambda x: x.modified_at, reverse=True)
    return EquityNotesDTO(ticker=ticker_upper, total_count=len(notes), items=notes)







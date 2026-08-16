import json
import os
import re
import shutil
from functools import lru_cache
from pathlib import Path
import frontmatter

from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.logger import get_logger

from .core import (
    VAULT_PATH,
    INDEX_PATH,
    INDEX_LOCK,
    _atomic_write_text,
    _VAULT_SYSTEM_FILES,
    _INDEX_EXCLUDE,
    _LINKED_CONTENT_LIMIT,
)
from .parser import _chunk_file


log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Runtime paths
# ---------------------------------------------------------------------------
#
# master_index.json
#     = canonical source-of-truth for Vault file registry
#
# .chroma_index
#     = derived semantic/vector index
#
# .chroma_mtime
#     = derived synchronization state for Chroma
#

CHROMA_PATH = VAULT_PATH / ".chroma_index"
_CHROMA_MTIME_FILE = VAULT_PATH / ".chroma_mtime"

_vs_cache: dict = {}
# {
#     "vs": Chroma,
#     "cache_signature": (...),
# }


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_embeddings():
    log.info(
        "กำลังโหลด embedding model สำหรับ SemanticSearch "
        "(ครั้งแรกอาจใช้เวลา)"
    )

    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )


# ---------------------------------------------------------------------------
# Master Index
# ---------------------------------------------------------------------------

def _load_master_index() -> dict:
    """
    โหลด canonical Master Index

    Source-of-truth:
        memories/.system/master_index.json

    IMPORTANT:
        ไม่ fallback ไป rglob() เพราะจะทำให้ Master Index
        ไม่ใช่ source-of-truth จริง
    """

    if not INDEX_PATH.exists():
        raise FileNotFoundError(
            f"Master Index ไม่พบ: {INDEX_PATH}"
        )

    try:
        data = json.loads(
            INDEX_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Master Index ไม่สามารถอ่านได้: {INDEX_PATH}"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Master Index ต้องเป็น JSON object: {INDEX_PATH}"
        )

    files = data.get("files")

    if not isinstance(files, list):
        raise RuntimeError(
            "Master Index ไม่มี 'files' list ที่ถูกต้อง"
        )

    return data


def _validate_master_index_record(record: object) -> str | None:
    """
    ตรวจ record จาก master_index.json

    Returns:
        relative path ถ้า valid
        None ถ้า invalid
    """

    if not isinstance(record, dict):
        return None

    relative_path = record.get("path")

    if not isinstance(relative_path, str):
        return None

    relative_path = relative_path.strip()

    if not relative_path:
        return None

    if not relative_path.lower().endswith(".md"):
        return None

    try:
        candidate = Path(relative_path)

        # ห้าม absolute path
        if candidate.is_absolute():
            return None

        resolved = (VAULT_PATH / candidate).resolve()
        vault_root = VAULT_PATH.resolve()

        # ป้องกัน path traversal
        resolved.relative_to(vault_root)

    except (OSError, RuntimeError, ValueError):
        return None

    return relative_path.replace("\\", "/")


def _searchable_files() -> list[Path]:
    """
    คืนรายชื่อ Markdown files จาก Master Index เท่านั้น

    IMPORTANT:
        ห้ามใช้ VAULT_PATH.rglob() ที่นี่

    Master Index = source-of-truth
    Filesystem    = existence validation
    Chroma        = derived semantic index
    """

    index = _load_master_index()

    records = index.get("files", [])

    files: list[Path] = []
    seen: set[str] = set()

    for record in records:
        relative_path = _validate_master_index_record(record)

        if relative_path is None:
            log.warning(
                "ข้าม Master Index record ที่ไม่ถูกต้อง: %r",
                record,
            )
            continue

        if relative_path in seen:
            continue

        file_path = VAULT_PATH / relative_path

        # Master Index เป็น registry แต่ filesystem เป็น existence check
        if not file_path.is_file():
            log.warning(
                "Master Index อ้างถึงไฟล์ที่ไม่มีอยู่จริง: %s",
                relative_path,
            )
            continue

        if file_path.name in _VAULT_SYSTEM_FILES:
            continue

        if any(
            excluded in file_path.parts
            for excluded in _INDEX_EXCLUDE
        ):
            continue

        seen.add(relative_path)
        files.append(file_path)

    return sorted(
        files,
        key=lambda path: str(
            path.relative_to(VAULT_PATH)
        ).lower(),
    )


# ---------------------------------------------------------------------------
# Chroma synchronization state
# ---------------------------------------------------------------------------

def _load_index_state() -> dict:
    """
    โหลด derived per-file Chroma state

    Structure:
        {
            "relative/path.md": {
                "mtime": float,
                "chunks": int
            }
        }

    IMPORTANT:
        นี่ไม่ใช่ Master Index
        ใช้เฉพาะสำหรับ synchronization ของ Chroma
    """

    if not _CHROMA_MTIME_FILE.exists():
        return {}

    try:
        data = json.loads(
            _CHROMA_MTIME_FILE.read_text(
                encoding="utf-8"
            )
        )

        if (
            isinstance(data, dict)
            and isinstance(data.get("files"), dict)
        ):
            return data["files"]

    except (OSError, json.JSONDecodeError):
        log.warning(
            "ไม่สามารถอ่าน Chroma mtime state: %s",
            _CHROMA_MTIME_FILE,
        )

    return {}


def _save_index_state(files: dict) -> None:
    """
    บันทึก derived Chroma synchronization state
    """

    _atomic_write_text(
        _CHROMA_MTIME_FILE,
        json.dumps(
            {
                "version": 1,
                "files": files,
            },
            ensure_ascii=False,
        ),
    )


# ---------------------------------------------------------------------------
# Semantic Search
# ---------------------------------------------------------------------------

@tool
def search_all_memories(keyword: str) -> str:
    """
    ค้นหาความจำทั้งหมดใน Vault ด้วย Semantic Search (Vector RAG) แบบ Local

    [Usage/When to use]
    ใช้เมื่อต้องการค้นหาข้อมูลจากคลังความรู้แต่ไม่ทราบชื่อไฟล์ชัดเจน

    เหมาะสำหรับ:
        - semantic / contextual search
        - คำถามเกี่ยวกับกลยุทธ์
        - การค้นหาความรู้จากหลายไฟล์

    หากต้องการเจาะ Entity และความสัมพันธ์:
        ใช้ search_graph_context()

    Master Index:
        memories/.system/master_index.json

    Chroma:
        memories/.chroma_index

    Chroma mtime state:
        memories/.chroma_mtime
    """

    try:
        md_files = _searchable_files()

    except (FileNotFoundError, RuntimeError) as exc:
        log.error("Master Index unavailable: %s", exc)

        return (
            "ไม่สามารถค้นหาได้: Master Index ใช้งานไม่ได้\n"
            f"รายละเอียด: {exc}"
        )

    if not md_files:
        return (
            "ไม่พบไฟล์ความจำที่สามารถค้นหาได้ "
            "จาก Master Index"
        )

    # -----------------------------------------------------------------------
    # Current filesystem state
    # -----------------------------------------------------------------------

    current: dict[str, dict] = {}

    for file_path in md_files:
        try:
            relative = str(
                file_path.relative_to(VAULT_PATH)
            ).replace("\\", "/")

            current[relative] = {
                "mtime": file_path.stat().st_mtime
            }

        except OSError as exc:
            log.warning(
                "ไม่สามารถอ่าน metadata ของไฟล์ %s: %s",
                file_path,
                exc,
            )

    if not current:
        return (
            "ไม่พบไฟล์ความจำที่สามารถอ่าน metadata ได้"
        )

    # -----------------------------------------------------------------------
    # Compare with derived Chroma state
    # -----------------------------------------------------------------------

    stored = _load_index_state()

    added_or_changed = [
        rel
        for rel, info in current.items()
        if (
            rel not in stored
            or abs(
                stored[rel].get("mtime", 0)
                - info["mtime"]
            ) > 1e-3
        )
    ]

    removed = [
        rel
        for rel in stored
        if rel not in current
    ]

    cache_valid = (
        _vs_cache.get("cache_signature")
        == (
            len(current),
            tuple(sorted(current)),
        )
    )

    needs_update = (
        bool(added_or_changed or removed)
        or not cache_valid
    )

    # -----------------------------------------------------------------------
    # Reuse cached vectorstore when possible
    # -----------------------------------------------------------------------

    if "vs" in _vs_cache and not needs_update:
        vectorstore = _vs_cache["vs"]

    else:
        try:
            vectorstore = (
                _vs_cache.get("vs")
                or Chroma(
                    persist_directory=str(CHROMA_PATH),
                    embedding_function=get_embeddings(),
                )
            )

        except Exception as exc:
            log.warning(
                "Chroma store เปิดไม่ได้ อาจเสียหาย: %s",
                exc,
            )

            # ---------------------------------------------------------------
            # Corrupted Chroma → rebuild derived index
            # ---------------------------------------------------------------

            if CHROMA_PATH.exists():
                try:
                    shutil.rmtree(CHROMA_PATH)
                except OSError as remove_exc:
                    return (
                        "เกิดข้อผิดพลาดในการลบ Chroma "
                        f"ที่เสียหาย: {remove_exc}"
                    )

            stored = {}
            added_or_changed = list(current)
            removed = []

            try:
                vectorstore = Chroma(
                    persist_directory=str(CHROMA_PATH),
                    embedding_function=get_embeddings(),
                )

            except Exception as rebuild_exc:
                return (
                    "เกิดข้อผิดพลาดในการสร้าง "
                    f"vectorstore ใหม่: {rebuild_exc}"
                )

        # -------------------------------------------------------------------
        # Delete removed / changed chunks
        # -------------------------------------------------------------------

        ids_to_delete: list[str] = []

        for rel in removed:
            chunk_count = stored.get(
                rel,
                {},
            ).get("chunks", 0)

            ids_to_delete.extend(
                f"{rel}::{i}"
                for i in range(chunk_count)
            )

        for rel in added_or_changed:
            chunk_count = stored.get(
                rel,
                {},
            ).get("chunks", 0)

            if chunk_count:
                ids_to_delete.extend(
                    f"{rel}::{i}"
                    for i in range(chunk_count)
                )

        if ids_to_delete:
            try:
                vectorstore.delete(
                    ids=ids_to_delete
                )

            except Exception as exc:
                log.warning(
                    "Chroma delete failed "
                    "(continuing): %s",
                    exc,
                )

        # -------------------------------------------------------------------
        # Re-chunk changed files
        # -------------------------------------------------------------------

        if added_or_changed:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
            )

            all_texts: list[str] = []
            all_metas: list[dict] = []
            all_ids: list[str] = []

            for rel in added_or_changed:
                file_path = VAULT_PATH / rel

                if not file_path.exists():
                    continue

                try:
                    texts, metas, ids = _chunk_file(
                        file_path,
                        splitter,
                    )

                except Exception as exc:
                    log.warning(
                        "ไม่สามารถ chunk %s: %s",
                        rel,
                        exc,
                    )
                    continue

                all_texts.extend(texts)
                all_metas.extend(metas)
                all_ids.extend(ids)

                current[rel]["chunks"] = len(texts)

            if all_texts:
                try:
                    vectorstore.add_texts(
                        texts=all_texts,
                        metadatas=all_metas,
                        ids=all_ids,
                    )

                except Exception as exc:
                    return (
                        "เกิดข้อผิดพลาดในการเพิ่ม "
                        f"vectorstore: {exc}"
                    )

        # -------------------------------------------------------------------
        # Preserve chunk counts for unchanged files
        # -------------------------------------------------------------------

        for rel in current:
            if (
                "chunks" not in current[rel]
                and rel in stored
            ):
                current[rel]["chunks"] = (
                    stored[rel].get("chunks", 0)
                )

        # -------------------------------------------------------------------
        # Save derived state
        # -------------------------------------------------------------------

        _save_index_state(current)

        _vs_cache["vs"] = vectorstore
        _vs_cache["cache_signature"] = (
            len(current),
            tuple(sorted(current)),
        )

    # -----------------------------------------------------------------------
    # Semantic query
    # -----------------------------------------------------------------------

    try:
        results = vectorstore.similarity_search(
            keyword,
            k=5,
        )

    except Exception as exc:
        return (
            "เกิดข้อผิดพลาดในการค้นหา: "
            f"{exc}"
        )

    if not results:
        return (
            f"ไม่พบความจำที่เกี่ยวข้องกับ "
            f"'{keyword}'"
        )

    parts = [
        f"ผลการค้นหาเชิงความหมายสำหรับ "
        f"'{keyword}' ({len(results)} ผลลัพธ์):\n"
    ]

    for i, doc in enumerate(results, 1):
        source = doc.metadata.get(
            "source",
            "ไม่ทราบแหล่งที่มา",
        )

        parts.append(
            f"--- ผลลัพธ์ที่ {i} | "
            f"แหล่งที่มา: [{source}] ---\n"
            f"{doc.page_content}\n"
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# File lookup
# ---------------------------------------------------------------------------

def _find_file_by_name(
    name: str,
    all_files: list[Path],
) -> Path | None:
    """
    ค้นหาไฟล์จาก registry ของ Master Index

    Priority:
        1. exact stem match
        2. partial stem match
    """

    name_lower = name.lower()

    exact = next(
        (
            file_path
            for file_path in all_files
            if file_path.stem.lower() == name_lower
        ),
        None,
    )

    if exact:
        return exact

    return next(
        (
            file_path
            for file_path in all_files
            if name_lower in file_path.stem.lower()
        ),
        None,
    )


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GraphRAG
# ---------------------------------------------------------------------------

def _load_graph_metadata(file_path: Path) -> dict:
    """
    Load frontmatter metadata for GraphRAG relationship resolution.

    Graph relationship source:
        Master Index -> determines candidate files
        frontmatter -> determines entity relationship

    This function intentionally does NOT scan the Vault.
    """

    try:
        post = frontmatter.load(file_path)
        metadata = dict(post.metadata)

        if not isinstance(metadata, dict):
            return {}

        return metadata

    except Exception as exc:
        log.warning(
            "ไม่สามารถอ่าน metadata สำหรับ GraphRAG: %s: %s",
            file_path,
            exc,
        )
        return {}


def _graph_file_priority(file_path: Path, metadata: dict) -> tuple:
    """
    Deterministic ordering for GraphRAG context.

    Priority:
        0 = stock entity
        1 = equity analysis
        2 = latest/current news
        3 = quant snapshot
        4 = other related knowledge
    """

    entity_type = str(
        metadata.get("entity_type", "")
    ).strip().lower()

    priority_map = {
        "stock_entity": 0,
        "equity_analysis": 1,
        "company_news": 2,
        "news": 2,
        "equity_quant_snapshot": 3,
    }

    priority = priority_map.get(entity_type, 4)

    date_value = metadata.get("date")

    if date_value is None:
        date_key = ""
    else:
        date_key = str(date_value)

    return (
        priority,
        date_key,
        file_path.name.lower(),
    )


def _resolve_graph_entity(
    entity_name: str,
    all_files: list[Path],
) -> tuple[Path | None, str | None]:
    """
    Resolve an investment entity deterministically.

    Resolution order:
        1. Exact entity filename/stem
        2. Exact ticker in frontmatter
        3. Case-insensitive entity filename

    Returns:
        (entity_file, ticker)
    """

    normalized = entity_name.strip().lower()

    if not normalized:
        return None, None

    # -----------------------------------------------------------------------
    # 1. Exact entity file match
    # -----------------------------------------------------------------------

    exact_file = next(
        (
            file_path
            for file_path in all_files
            if file_path.stem.lower() == normalized
        ),
        None,
    )

    if exact_file is not None:
        metadata = _load_graph_metadata(exact_file)

        entity_type = str(
            metadata.get("entity_type", "")
        ).strip().lower()

        ticker = str(
            metadata.get("ticker", "")
        ).strip().upper()

        if entity_type == "stock_entity" and ticker:
            return exact_file, ticker

    # -----------------------------------------------------------------------
    # 2. Exact ticker metadata match
    # -----------------------------------------------------------------------

    for file_path in all_files:
        metadata = _load_graph_metadata(file_path)

        entity_type = str(
            metadata.get("entity_type", "")
        ).strip().lower()

        ticker = str(
            metadata.get("ticker", "")
        ).strip().upper()

        if (
            entity_type == "stock_entity"
            and ticker
            and ticker.lower() == normalized
        ):
            return file_path, ticker

    return None, None


@tool
def search_graph_context(entity_name: str) -> str:
    """
    Resolve an investment entity and construct deterministic GraphRAG context.

    Architecture:

        Master Index
            |
            +-- Entity Registry
            |
            +-- ticker relationship
                    |
                    +-- Equity Analysis
                    +-- Company News
                    +-- Quant Snapshot
                    +-- Other related knowledge

    IMPORTANT:
        - Master Index is the file registry source-of-truth.
        - Filesystem is used only for existence/read validation.
        - Frontmatter ticker is the relationship key.
        - Wikilinks are NOT required.
        - No Vault-wide rglob() is used here.
        - Chroma is NOT used for graph relationship resolution.
    """

    # -----------------------------------------------------------------------
    # Step 1: Load searchable files from Master Index
    # -----------------------------------------------------------------------

    try:
        all_files = _searchable_files()

    except (FileNotFoundError, RuntimeError) as exc:
        log.error(
            "Master Index unavailable for GraphRAG: %s",
            exc,
        )

        return (
            "ไม่สามารถค้นหา Graph Context ได้: "
            f"{exc}"
        )

    if not all_files:
        return (
            "ไม่พบไฟล์ความจำที่สามารถค้นหาได้ "
            "จาก Master Index"
        )

    # -----------------------------------------------------------------------
    # Step 2: Resolve canonical entity
    # -----------------------------------------------------------------------

    main_file, ticker = _resolve_graph_entity(
        entity_name,
        all_files,
    )

    if main_file is None or not ticker:
        return (
            f"ไม่พบ investment entity สำหรับ "
            f"'{entity_name}' ใน Master Index"
        )

    # -----------------------------------------------------------------------
    # Step 3: Read main entity
    # -----------------------------------------------------------------------

    try:
        main_content = main_file.read_text(
            encoding="utf-8"
        )

    except OSError as exc:
        return (
            f"ไม่สามารถอ่านไฟล์ entity "
            f"'{entity_name}': {exc}"
        )

    main_metadata = _load_graph_metadata(main_file)

    # -----------------------------------------------------------------------
    # Step 4: Resolve related files by ticker
    #
    # IMPORTANT:
    # Do NOT depend on Wikilinks.
    # Every knowledge file carrying the same ticker belongs to the graph.
    # -----------------------------------------------------------------------

    related_files: list[tuple[Path, dict]] = []

    for file_path in all_files:
        if file_path == main_file:
            continue

        metadata = _load_graph_metadata(file_path)

        related_ticker = str(
            metadata.get("ticker", "")
        ).strip().upper()

        if not related_ticker:
            continue

        if related_ticker != ticker:
            continue

        related_files.append(
            (file_path, metadata)
        )

    # -----------------------------------------------------------------------
    # Step 5: Deterministic ordering
    # -----------------------------------------------------------------------

    related_files.sort(
        key=lambda item: _graph_file_priority(
            item[0],
            item[1],
        )
    )

    # -----------------------------------------------------------------------
    # Step 6: Build Graph Context
    # -----------------------------------------------------------------------

    output_parts: list[str] = []

    output_parts.append(
        "=" * 80
    )

    output_parts.append(
        f"GRAPH CONTEXT: {ticker}"
    )

    output_parts.append(
        "=" * 80
    )

    output_parts.append(
        "\n[ENTITY]\n"
        f"Name: {main_file.stem}\n"
        f"Ticker: {ticker}\n"
        f"Entity Type: "
        f"{main_metadata.get('entity_type', 'unknown')}\n"
        f"Source: {main_file.relative_to(VAULT_PATH)}\n"
    )

    output_parts.append(
        "\n--- Entity Content ---\n"
        f"{main_content}\n"
    )

    # -----------------------------------------------------------------------
    # Step 7: Group related knowledge by type
    # -----------------------------------------------------------------------

    grouped: dict[str, list[tuple[Path, dict]]] = {
        "equity_analysis": [],
        "company_news": [],
        "equity_quant_snapshot": [],
        "other": [],
    }

    for file_path, metadata in related_files:
        entity_type = str(
            metadata.get("entity_type", "")
        ).strip().lower()

        if entity_type == "equity_analysis":
            grouped["equity_analysis"].append(
                (file_path, metadata)
            )

        elif entity_type in {
            "company_news",
            "news",
        }:
            grouped["company_news"].append(
                (file_path, metadata)
            )

        elif entity_type == "equity_quant_snapshot":
            grouped["equity_quant_snapshot"].append(
                (file_path, metadata)
            )

        else:
            grouped["other"].append(
                (file_path, metadata)
            )

    # -----------------------------------------------------------------------
    # Step 8: Render grouped context
    # -----------------------------------------------------------------------

    sections = [
        (
            "EQUITY ANALYSIS",
            grouped["equity_analysis"],
        ),
        (
            "NEWS",
            grouped["company_news"],
        ),
        (
            "QUANT SNAPSHOT",
            grouped["equity_quant_snapshot"],
        ),
        (
            "OTHER RELATED KNOWLEDGE",
            grouped["other"],
        ),
    ]

    total_related = 0

    for section_name, files in sections:

        if not files:
            continue

        output_parts.append(
            f"\n{'-' * 80}\n"
            f"[{section_name}]\n"
            f"{'-' * 80}\n"
        )

        for file_path, metadata in files:
            total_related += 1

            try:
                content = file_path.read_text(
                    encoding="utf-8"
                )

            except OSError as exc:
                output_parts.append(
                    f"\n[{file_path.name}]\n"
                    f"(ไม่สามารถอ่านไฟล์: {exc})\n"
                )
                continue

            # Prevent one enormous document from overwhelming
            # the agent context.
            if len(content) > _LINKED_CONTENT_LIMIT:
                content = (
                    content[
                        :_LINKED_CONTENT_LIMIT
                    ]
                    + "\n...[ตัดทอน]"
                )

            date_value = metadata.get(
                "date",
                "unknown",
            )

            output_parts.append(
                f"\n### {file_path.stem}\n"
                f"Entity Type: "
                f"{metadata.get('entity_type', 'unknown')}\n"
                f"Date: {date_value}\n"
                f"Source: "
                f"{file_path.relative_to(VAULT_PATH)}\n\n"
                f"{content}\n"
            )

    # -----------------------------------------------------------------------
    # Step 9: Graph summary
    # -----------------------------------------------------------------------

    output_parts.append(
        "\n"
        + "=" * 80
    )

    output_parts.append(
        "GRAPH SUMMARY"
    )

    output_parts.append(
        "=" * 80
    )

    output_parts.append(
        f"Entity: {ticker}\n"
        f"Related files: {total_related}\n"
        f"Equity Analysis: "
        f"{len(grouped['equity_analysis'])}\n"
        f"News: "
        f"{len(grouped['company_news'])}\n"
        f"Quant Snapshots: "
        f"{len(grouped['equity_quant_snapshot'])}\n"
        f"Other: "
        f"{len(grouped['other'])}"
    )

    return "\n".join(output_parts)

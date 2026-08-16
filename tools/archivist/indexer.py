from datetime import datetime
import json
import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from core.logger import get_logger

from .core import (
    _atomic_write_text,
    VAULT_PATH,
    INDEX_PATH,
    INDEX_LOCK,
    _VAULT_SYSTEM_FILES,
    _INDEX_EXCLUDE,
)
from .parser import extract_yaml_frontmatter_value

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Runtime configuration
# ---------------------------------------------------------------------------

VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", "./memories"))
INDEX_PATH = VAULT_PATH / ".system" / "master_index.json"
INDEX_LOCK = str(INDEX_PATH) + ".lock"


# ---------------------------------------------------------------------------
# Runtime cache
# ---------------------------------------------------------------------------

_index_cache: dict[str, list[tuple[str, str]]] = {}
_index_cache_built = False
_index_dirty = False

_LAYER1_ENTITY_TYPES = {"stock_entity"}


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def _read_entity_type(file_path: Path) -> str:
    """ดึง entity_type จาก YAML frontmatter ของไฟล์ Markdown"""
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return "—"

    value = extract_yaml_frontmatter_value(content, "entity_type")
    return value if value else "—"


def _file_folder_label(
    file_path: Path,
    vault_root: Optional[Path | str] = None,
) -> str:
    """คืนค่า folder path แบบ relative ต่อ Vault"""
    root = Path(vault_root) if vault_root else VAULT_PATH

    try:
        rel = file_path.resolve().relative_to(root.resolve())

        if rel.parent == Path("."):
            return "Root"

        return str(rel.parent).replace("\\", "/")

    except (ValueError, RuntimeError):
        try:
            rel = file_path.resolve().relative_to(VAULT_PATH.resolve())

            if rel.parent == Path("."):
                return "Root"

            return str(rel.parent).replace("\\", "/")

        except (ValueError, RuntimeError):
            parts = file_path.parts

            for marker in (
                "30_Knowledge_Base",
                "10_Projects",
                "20_Areas",
                "40_Archive",
                "00_Inbox",
                "01_Daily_Logs",
                "50_Crypto",
                "60_Research",
            ):
                if marker in parts:
                    idx = parts.index(marker)
                    rel_parts = parts[idx:-1]

                    if rel_parts:
                        return "/".join(rel_parts)

                    return marker

            return file_path.parent.name or "Root"


def _is_indexable(file_path: Path) -> bool:
    """ตรวจว่าไฟล์ Markdown นี้ควรเข้า Master Index หรือไม่"""
    return (
        file_path.name not in _VAULT_SYSTEM_FILES
        and not any(
            excluded in file_path.parts
            for excluded in _INDEX_EXCLUDE
        )
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _build_cache_from_disk(
    vault_root: Optional[Path | str] = None,
) -> None:
    """Full scan ของ Markdown files ใน Vault"""
    global _index_cache_built

    _index_cache.clear()

    root = Path(vault_root) if vault_root else VAULT_PATH

    if not root.exists():
        _index_cache_built = True
        return

    all_files = [
        file_path
        for file_path in sorted(root.rglob("*.md"))
        if _is_indexable(file_path)
    ]

    for file_path in all_files:
        folder = _file_folder_label(
            file_path,
            vault_root=root,
        )

        entity_type = _read_entity_type(file_path)

        _index_cache.setdefault(folder, []).append(
            (file_path.stem, entity_type)
        )

    _index_cache_built = True


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _entity_category(folder: str) -> str:
    """
    แยก category จาก folder path

    ตัวอย่าง:
        30_Knowledge_Base/Stocks/AAPL
        → Stocks
    """
    parts = folder.replace("\\", "/").split("/")

    for index, part in enumerate(parts):
        if (
            part == "30_Knowledge_Base"
            and index + 1 < len(parts)
        ):
            return parts[index + 1]

    return "Other"


# ---------------------------------------------------------------------------
# Structured master index
# ---------------------------------------------------------------------------

def _build_master_index_payload(
    vault_root: Optional[Path | str] = None,
) -> dict:
    """
    สร้าง machine-readable Master Index

    master_index.json เป็น source-of-truth สำหรับระบบ
    ส่วน index.md เป็น human-readable projection
    """

    root = Path(vault_root) if vault_root else VAULT_PATH

    entities: list[dict] = []
    knowledge: list[dict] = []
    files: list[dict] = []

    for folder in sorted(_index_cache):
        entries = _index_cache[folder]

        for stem, entity_type in sorted(entries):
            relative_path = (
                f"{folder}/{stem}.md"
                if folder != "Root"
                else f"{stem}.md"
            )

            category = _entity_category(folder)

            record = {
                "name": stem,
                "path": relative_path.replace("\\", "/"),
                "folder": folder,
                "entity_type": entity_type,
                "category": category,
            }

            files.append(record)

            if entity_type in _LAYER1_ENTITY_TYPES:
                entities.append(record.copy())
            else:
                knowledge.append(record.copy())

    return {
        "version": 1,
        "title": "Master Index",
        "generated_at": datetime.now().isoformat(),
        "vault": str(root),
        "totals": {
            "files": len(files),
            "entities": len(entities),
            "knowledge": len(knowledge),
        },
        "entities": entities,
        "knowledge": knowledge,
        "files": files,
    }


def _write_master_index_json(
    vault_root: Optional[Path | str] = None,
    payload: Optional[dict] = None,
) -> None:
    """เขียน machine-readable master_index.json"""
    root = Path(vault_root) if vault_root else VAULT_PATH
    index_path = root / ".system" / "master_index.json"

    index_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if payload is None:
        payload = _build_master_index_payload(
            vault_root=root
        )

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )

    _atomic_write_text(
        index_path,
        serialized,
    )


# ---------------------------------------------------------------------------
# Human-readable Markdown projection
# ---------------------------------------------------------------------------

def _write_index_markdown(
    vault_root: Optional[Path | str] = None,
    payload: Optional[dict] = None,
) -> str:
    """
    สร้าง index.md สำหรับ Obsidian / human navigation

    หมายเหตุ:
        index.md ไม่ใช่ machine source-of-truth
        master_index.json ต่างหากคือ source-of-truth
    """

    root = Path(vault_root) if vault_root else VAULT_PATH

    if payload is None:
        payload = _build_master_index_payload(
            vault_root=root
        )

    entities = payload["entities"]
    knowledge = payload["knowledge"]

    lines = [
        "---",
        "title: Master Index",
        f"date: {datetime.now().strftime('%Y-%m-%d')}",
        "source_of_truth: .system/master_index.json",
        "---",
        "",
        "# Master Index",
        "",
        "> Machine source-of-truth: `.system/master_index.json`",
        ">",
        "> ระบบ 3-Layer Graph View:",
        "> **Entities** = Layer 1 hubs",
        "> **Knowledge** = Layer 2 snapshots/news",
        "> **Portfolio** = Layer 3",
        "",
    ]

    # -----------------------------------------------------------------------
    # Layer 1
    # -----------------------------------------------------------------------

    if entities:
        lines += [
            "## 📍 Entities (Layer 1 Hubs)",
            "",
        ]

        entities_by_category: dict[str, list[dict]] = {}

        for entity in entities:
            entities_by_category.setdefault(
                entity["category"],
                [],
            ).append(entity)

        for category in sorted(entities_by_category):
            category_entities = sorted(
                entities_by_category[category],
                key=lambda item: item["name"],
            )

            lines += [
                f"### {category} ({len(category_entities)})",
                "",
            ]

            wikilinks = " · ".join(
                f"[[{item['name']}]]"
                for item in category_entities
            )

            lines += [
                wikilinks,
                "",
            ]

    # -----------------------------------------------------------------------
    # Layer 2
    # -----------------------------------------------------------------------

    if knowledge:
        lines += [
            "## 📚 Knowledge (Layer 2 Snapshots)",
            "",
        ]

        knowledge_by_folder: dict[str, list[dict]] = {}

        for item in knowledge:
            knowledge_by_folder.setdefault(
                item["folder"],
                [],
            ).append(item)

        for folder in sorted(knowledge_by_folder):
            items = sorted(
                knowledge_by_folder[folder],
                key=lambda item: item["name"],
                reverse=True,
            )

            lines += [
                f"### {folder}",
                "",
                "| File | Entity Type |",
                "|------|-------------|",
            ]

            for item in items:
                lines.append(
                    f"| [[{item['name']}]] | "
                    f"{item['entity_type']} |"
                )

            lines.append("")

    target = root / "index.md"

    _atomic_write_text(
        target,
        "\n".join(lines),
    )

    return str(target)


# ---------------------------------------------------------------------------
# Unified index writer
# ---------------------------------------------------------------------------

def _write_all_indexes(
    vault_root: Optional[Path | str] = None,
) -> str:
    """
    เขียนทั้ง machine index และ human-readable projection

    master_index.json = source-of-truth
    index.md           = projection
    """

    root = Path(vault_root) if vault_root else VAULT_PATH

    payload = _build_master_index_payload(
        vault_root=root
    )

    _write_master_index_json(
        vault_root=root,
        payload=payload,
    )

    _write_index_markdown(
        vault_root=root,
        payload=payload,
    )

    totals = payload["totals"]

    return (
        f"อัปเดต Master Index สำเร็จ: "
        f"{totals['files']} ไฟล์ "
        f"({totals['entities']} entities, "
        f"{totals['knowledge']} snapshots)"
    )


# ---------------------------------------------------------------------------
# Incremental upsert
# ---------------------------------------------------------------------------

def _index_upsert(
    file_path: Path,
    vault_root: Optional[Path | str] = None,
) -> None:
    """
    Incremental update cache

    ไม่เขียน disk ทันที
    จะ mark dirty แล้ว flush ภายหลัง
    """
    global _index_dirty

    if not _is_indexable(file_path):
        return

    if not _index_cache_built:
        _build_cache_from_disk(
            vault_root=vault_root
        )

    folder = _file_folder_label(
        file_path,
        vault_root=vault_root,
    )

    entity_type = _read_entity_type(file_path)

    entries = _index_cache.setdefault(
        folder,
        [],
    )

    for index, (stem, _) in enumerate(entries):
        if stem == file_path.stem:
            entries[index] = (
                file_path.stem,
                entity_type,
            )
            break
    else:
        entries.append(
            (
                file_path.stem,
                entity_type,
            )
        )

    _index_dirty = True


def flush_index_if_dirty(
    vault_root: Optional[Path | str] = None,
) -> str | None:
    """
    Flush cache ถ้ามีการเปลี่ยนแปลง

    จะเขียน:
        .system/master_index.json
        index.md
    """

    global _index_dirty

    if not _index_dirty:
        return None

    message = _write_all_indexes(
        vault_root=vault_root
    )

    _index_dirty = False

    return message


# ---------------------------------------------------------------------------
# Full rebuild
# ---------------------------------------------------------------------------

def _rebuild_index() -> str:
    """Full rebuild จาก disk"""
    global _index_dirty

    _build_cache_from_disk()

    message = _write_all_indexes()

    _index_dirty = False

    return message


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool
def update_master_index() -> str:
    """
    สร้างหรืออัปเดต Master Index

    Source of truth:
        memories/.system/master_index.json

    Human-readable projection:
        memories/index.md

    [Usage/When to use]
    ใช้เมื่อมีการเปลี่ยนแปลงโครงสร้างไฟล์อย่างมีนัยสำคัญ
    เช่น:
        - เพิ่มไฟล์หลายไฟล์
        - ลบไฟล์
        - เปลี่ยนชื่อไฟล์
        - ต้องการ resync Vault ทั้งหมด

    ไม่จำเป็นต้องเรียกเมื่อเขียนไฟล์เดียวผ่าน writer
    เพราะ writer ใช้ _index_upsert() อยู่แล้ว

    Returns:
        str: สถานะการ rebuild พร้อมจำนวนไฟล์
    """
    return _rebuild_index()

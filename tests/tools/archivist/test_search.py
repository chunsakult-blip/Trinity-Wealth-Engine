import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.archivist.search import (
    search_all_memories,
    search_graph_context,
)
import tools.archivist.search as search_module


@pytest.fixture
def test_vault(tmp_path, monkeypatch):
    vault_dir = tmp_path / "memories"
    vault_dir.mkdir(parents=True, exist_ok=True)

    import tools.archivist.core as core_m
    import tools.archivist.writer as writer_m
    import tools.archivist.indexer as indexer_m
    import tools.archivist.search as search_m
    import tools.archivist.linter as linter_m
    import tools.archivist.parser as parser_m

    modules = [
        core_m,
        writer_m,
        indexer_m,
        search_m,
        linter_m,
        parser_m,
    ]

    # ------------------------------------------------------------------
    # Test-local Vault
    # ------------------------------------------------------------------

    monkeypatch.setattr(
        core_m,
        "VAULT_PATH",
        vault_dir,
    )
    monkeypatch.setattr(
        core_m,
        "INDEX_PATH",
        vault_dir / ".system" / "master_index.json",
    )
    monkeypatch.setattr(
        core_m,
        "INDEX_LOCK",
        str(vault_dir / ".system" / "master_index.json.lock"),
    )

    # ------------------------------------------------------------------
    # Patch every Archivist module that imported these paths
    # ------------------------------------------------------------------

    for mod in modules:
        monkeypatch.setattr(
            mod,
            "VAULT_PATH",
            vault_dir,
            raising=False,
        )

    monkeypatch.setattr(
        search_m,
        "INDEX_PATH",
        vault_dir / ".system" / "master_index.json",
        raising=False,
    )
    monkeypatch.setattr(
        search_m,
        "INDEX_LOCK",
        str(vault_dir / ".system" / "master_index.json.lock"),
        raising=False,
    )
    monkeypatch.setattr(
        search_m,
        "CHROMA_PATH",
        vault_dir / ".chroma_index",
        raising=False,
    )
    monkeypatch.setattr(
        search_m,
        "_CHROMA_MTIME_FILE",
        vault_dir / ".chroma_mtime",
        raising=False,
    )

    # ------------------------------------------------------------------
    # Reset Chroma cache
    # ------------------------------------------------------------------

    search_m._vs_cache.clear()

    return vault_dir


def _write_master_index(vault: Path, *relative_paths: str) -> None:
    index_path = vault / ".system" / "master_index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "files": [
                    {"path": path}
                    for path in relative_paths
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ======================================================================
# Semantic Search
# ======================================================================


@patch("tools.archivist.search.Chroma")
@patch("tools.archivist.search.get_embeddings")
def test_search_all_memories_basic(
    mock_embeddings,
    mock_chroma_class,
    test_vault,
):
    mock_embeddings.return_value = MagicMock()

    mock_vs = MagicMock()

    mock_doc = MagicMock()
    mock_doc.page_content = "Test content"
    mock_doc.metadata = {"source": "test.md"}

    mock_vs.similarity_search.return_value = [mock_doc]
    mock_chroma_class.return_value = mock_vs

    # ------------------------------------------------------------------
    # Empty Vault / empty Master Index
    # ------------------------------------------------------------------

    _write_master_index(test_vault)

    res = search_all_memories.func("test")

    assert (
        "ไม่พบไฟล์ความจำที่สามารถค้นหาได้" in res
        or "ยังไม่มีไฟล์ความจำใด" in res
    )

    # ------------------------------------------------------------------
    # Add file + register in Master Index
    # ------------------------------------------------------------------

    test_file = test_vault / "test.md"
    test_file.write_text(
        "Hello World",
        encoding="utf-8",
    )

    _write_master_index(
        test_vault,
        "test.md",
    )

    # Master Index changed → clear derived cache/state
    search_module._vs_cache.clear()

    res = search_all_memories.func("test keyword")

    assert "ผลการค้นหาเชิงความหมาย" in res
    assert "Test content" in res

    # ------------------------------------------------------------------
    # Cache hit
    # ------------------------------------------------------------------

    res2 = search_all_memories.func("test keyword")

    assert "ผลการค้นหาเชิงความหมาย" in res2

    # ------------------------------------------------------------------
    # No semantic results
    # ------------------------------------------------------------------

    mock_vs.similarity_search.return_value = []

    res_empty = search_all_memories.func("test keyword")

    assert "ไม่พบความจำที่เกี่ยวข้องกับ" in res_empty


@patch("tools.archivist.search.Chroma")
@patch("tools.archivist.search.get_embeddings")
def test_search_all_memories_updates(
    mock_embeddings,
    mock_chroma_class,
    test_vault,
):
    mock_embeddings.return_value = MagicMock()

    mock_vs = MagicMock()
    mock_chroma_class.return_value = mock_vs

    f1 = test_vault / "f1.md"
    f2 = test_vault / "f2.md"

    f1.write_text(
        "Old content",
        encoding="utf-8",
    )
    f2.write_text(
        "F2 content",
        encoding="utf-8",
    )

    _write_master_index(
        test_vault,
        "f1.md",
        "f2.md",
    )

    # ------------------------------------------------------------------
    # First index
    # ------------------------------------------------------------------

    search_all_memories.func("test")

    assert mock_vs.add_texts.called

    mock_vs.reset_mock()

    # ------------------------------------------------------------------
    # Remove f2 + modify f1
    # ------------------------------------------------------------------

    f2.unlink()

    time.sleep(0.02)

    f1.write_text(
        "New content",
        encoding="utf-8",
    )

    _write_master_index(
        test_vault,
        "f1.md",
    )

    search_all_memories.func("test")

    # Removed f2 + changed f1 must trigger delete
    assert mock_vs.delete.called

    # Changed f1 must be re-added
    assert mock_vs.add_texts.called

    # ------------------------------------------------------------------
    # Similarity search error
    # ------------------------------------------------------------------

    mock_vs.similarity_search.side_effect = Exception(
        "search error"
    )

    res_err = search_all_memories.func("test")

    assert "เกิดข้อผิดพลาดในการค้นหา:" in res_err


# ======================================================================
# GraphRAG
# ======================================================================


def test_search_graph_context(
    test_vault,
):
    # ------------------------------------------------------------------
    # No Master Index records
    # ------------------------------------------------------------------

    _write_master_index(test_vault)

    res = search_graph_context.func("AAPL")

    assert (
        "ไม่พบไฟล์ความจำที่สามารถค้นหาได้" in res
        or "ยังไม่มีไฟล์ความจำใด" in res
    )

    # ------------------------------------------------------------------
    # Canonical stock entity
    # ------------------------------------------------------------------

    entity_file = test_vault / "Apple Inc.md"

    entity_file.write_text(
        "---\n"
        "entity_type: stock_entity\n"
        "ticker: AAPL\n"
        "date: 2026-08-18\n"
        "---\n"
        "Apple Inc. canonical entity.\n",
        encoding="utf-8",
    )

    analysis_file = test_vault / "AAPL Equity Analysis.md"

    analysis_file.write_text(
        "---\n"
        "entity_type: equity_analysis\n"
        "ticker: AAPL\n"
        "date: 2026-08-17\n"
        "---\n"
        "Apple equity analysis content.\n",
        encoding="utf-8",
    )

    news_file = test_vault / "AAPL News.md"

    news_file.write_text(
        "---\n"
        "entity_type: company_news\n"
        "ticker: AAPL\n"
        "date: 2026-08-18\n"
        "---\n"
        "Apple company news content.\n",
        encoding="utf-8",
    )

    quant_file = test_vault / "AAPL Quant Snapshot.md"

    quant_file.write_text(
        "---\n"
        "entity_type: equity_quant_snapshot\n"
        "ticker: AAPL\n"
        "date: 2026-08-18\n"
        "---\n"
        "Apple quant snapshot content.\n",
        encoding="utf-8",
    )

    unrelated_file = test_vault / "MSFT Analysis.md"

    unrelated_file.write_text(
        "---\n"
        "entity_type: equity_analysis\n"
        "ticker: MSFT\n"
        "date: 2026-08-18\n"
        "---\n"
        "Microsoft content must not appear.\n",
        encoding="utf-8",
    )

    _write_master_index(
        test_vault,
        "Apple Inc.md",
        "AAPL Equity Analysis.md",
        "AAPL News.md",
        "AAPL Quant Snapshot.md",
        "MSFT Analysis.md",
    )

    # ------------------------------------------------------------------
    # Graph resolution
    # ------------------------------------------------------------------

    res = search_graph_context.func("Apple Inc")

    assert "GRAPH CONTEXT: AAPL" in res
    assert "[ENTITY]" in res
    assert "Name: Apple Inc" in res
    assert "Ticker: AAPL" in res
    assert "Entity Type: stock_entity" in res

    # Entity content
    assert "Apple Inc. canonical entity." in res

    # Related knowledge
    assert "EQUITY ANALYSIS" in res
    assert "Apple equity analysis content." in res

    assert "NEWS" in res
    assert "Apple company news content." in res

    assert "QUANT SNAPSHOT" in res
    assert "Apple quant snapshot content." in res

    # Different ticker must not enter graph
    assert "Microsoft content must not appear." not in res

    # Summary
    assert "GRAPH SUMMARY" in res
    assert "Entity: AAPL" in res
    assert "Related files: 3" in res
    assert "Equity Analysis: 1" in res
    assert "News: 1" in res
    assert "Quant Snapshots: 1" in res

    # ------------------------------------------------------------------
    # Resolve by ticker
    # ------------------------------------------------------------------

    res_by_ticker = search_graph_context.func("AAPL")

    assert "GRAPH CONTEXT: AAPL" in res_by_ticker
    assert "Apple Inc. canonical entity." in res_by_ticker

    # ------------------------------------------------------------------
    # Unknown entity
    # ------------------------------------------------------------------

    res_not_found = search_graph_context.func(
        "NOT_A_REAL_ENTITY"
    )

    assert "ไม่พบ investment entity สำหรับ" in res_not_found

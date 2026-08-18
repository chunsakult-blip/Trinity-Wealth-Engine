import pytest
from unittest.mock import patch


@pytest.fixture
def isolated_archivist(tmp_path, monkeypatch):
    """
    Isolate every Archivist module to the same temporary Vault.

    Archivist runtime configuration is owned by core.py.
    Tests must patch every module-local imported reference because
    several modules import configuration symbols directly.
    """

    vault_dir = tmp_path

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
    # Core runtime configuration
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
    # Patch imported configuration references
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
        indexer_m,
        "INDEX_PATH",
        vault_dir / ".system" / "master_index.json",
        raising=False,
    )

    monkeypatch.setattr(
        indexer_m,
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
    # Reset runtime caches
    # ------------------------------------------------------------------

    search_m._vs_cache.clear()

    if hasattr(indexer_m, "_index_cache"):
        indexer_m._index_cache.clear()

    if hasattr(indexer_m, "_index_cache_built"):
        indexer_m._index_cache_built = False

    if hasattr(indexer_m, "_index_dirty"):
        indexer_m._index_dirty = False

    # ------------------------------------------------------------------
    # Return the same public Archivist tool surface used by tests
    # ------------------------------------------------------------------

    from tools.archivist.core import (
        init_vault_structure,
        read_file,
    )
    from tools.archivist.writer import (
        save_memory,
        write_raw_markdown,
    )
    from tools.archivist.indexer import (
        update_master_index,
    )
    from tools.archivist.search import (
        search_all_memories,
        search_graph_context,
    )
    from tools.archivist.linter import (
        lint_structural_health,
        lint_semantic_conflict,
    )

    return type(
        "IsolatedArchivist",
        (),
        {
            "init_vault_structure": init_vault_structure,
            "read_file": read_file,
            "save_memory": save_memory,
            "write_raw_markdown": write_raw_markdown,
            "update_master_index": update_master_index,
            "search_all_memories": search_all_memories,
            "search_graph_context": search_graph_context,
            "lint_structural_health": lint_structural_health,
            "lint_semantic_conflict": lint_semantic_conflict,
        },
    )()


@pytest.fixture
def tmp_vault(tmp_path):
    return tmp_path


def test_save_memory_new(isolated_archivist, tmp_vault):
    res = isolated_archivist.save_memory.invoke({
        "title": "Test Memory",
        "content": "This is a test content.",
        "folder_path": "30_Knowledge_Base/Stocks",
        "tags": ["test"],
        "entity_type": "Concept",
        "aliases": ["TM"],
        "linked_files": ["Linked_Doc"],
    })

    assert "บันทึกสำเร็จ (new)" in res

    saved_file = (
        tmp_vault
        / "30_Knowledge_Base"
        / "Stocks"
        / "Test Memory.md"
    )

    assert saved_file.exists()

    content = saved_file.read_text(encoding="utf-8")

    assert "entity_type: Concept" in content
    assert "tags:" in content
    assert "This is a test content." in content
    assert "[[Linked_Doc]]" in content


def test_write_raw_markdown(isolated_archivist, tmp_vault):
    raw_md = (
        "---\n"
        "title: Raw Test\n"
        "entity_type: test\n"
        "date: 2026-06-20\n"
        "---\n"
        "# Content"
    )

    res = isolated_archivist.write_raw_markdown.invoke({
        "content": raw_md,
        "folder_path": "30_Knowledge_Base/Macroeconomics",
        "filename": "Raw_Test_File",
    })

    assert "บันทึกสำเร็จ (raw" in res

    saved_file = (
        tmp_vault
        / "30_Knowledge_Base"
        / "Macroeconomics"
        / "Raw_Test_File.md"
    )

    assert saved_file.exists()
    assert saved_file.read_text(encoding="utf-8") == raw_md


def test_read_file(isolated_archivist, tmp_vault):
    target = tmp_vault / "Read_Test.md"
    target.write_text("Hello World", encoding="utf-8")

    res = isolated_archivist.read_file.invoke({
        "filepath": "Read_Test.md",
    })

    assert "=== Read_Test.md ===" in res
    assert "Hello World" in res


def test_read_file_not_found(isolated_archivist):
    res = isolated_archivist.read_file.invoke({
        "filepath": "Not_Exist.md",
    })

    assert "ไม่พบไฟล์" in res


def test_update_master_index(isolated_archivist, tmp_vault):
    """
    Current contract:
        Master Index is .system/master_index.json

    The legacy index.md contract is intentionally not tested.
    """

    knowledge_dir = tmp_vault / "30_Knowledge_Base"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    entity_file = knowledge_dir / "Test_Entity.md"

    entity_file.write_text(
        "---\n"
        "entity_type: stock_entity\n"
        "ticker: TEST\n"
        "---\n"
        "Test",
        encoding="utf-8",
    )

    res = isolated_archivist.update_master_index.invoke({})

    assert "อัปเดต Master Index สำเร็จ" in res

    index_file = (
        tmp_vault
        / ".system"
        / "master_index.json"
    )

    assert index_file.exists()

    index_data = index_file.read_text(
        encoding="utf-8"
    )

    assert "Test_Entity.md" in index_data
    assert "stock_entity" in index_data


def test_lint_structural_health(isolated_archivist, tmp_vault):
    (tmp_vault / "Orphan.md").write_text(
        "Just some text",
        encoding="utf-8",
    )

    (tmp_vault / "Empty.md").write_text(
        "",
        encoding="utf-8",
    )

    (tmp_vault / "Linked.md").write_text(
        "Links to [[Orphan]]",
        encoding="utf-8",
    )

    res = isolated_archivist.lint_structural_health.invoke({})

    assert "Vault Health Report" in res
    assert "Empty Files" in res
    assert "Empty" in res
    assert "Orphan" in res


def test_lint_semantic_conflict(isolated_archivist, tmp_vault):
    folder = tmp_vault / "TestFolder"
    folder.mkdir()

    (folder / "file1.md").write_text(
        "Fact A",
        encoding="utf-8",
    )

    (folder / "file2.md").write_text(
        "Fact B",
        encoding="utf-8",
    )

    res = isolated_archivist.lint_semantic_conflict.invoke({
        "target_folder_or_entity": "TestFolder",
    })

    assert "Semantic Conflict Check" in res
    assert "Fact A" in res
    assert "Fact B" in res


@patch("tools.archivist.search._searchable_files")
def test_search_all_memories(
    mock_searchable,
    isolated_archivist,
):
    mock_searchable.return_value = []

    res = isolated_archivist.search_all_memories.invoke({
        "keyword": "test",
    })

    assert len(res) > 0


def test_search_graph_context(isolated_archivist, tmp_vault):
    """
    Current GraphRAG contract:

        Master Index
            -> stock entity
            -> ticker
            -> related knowledge

    Wikilinks are not used for graph resolution.
    """

    knowledge_dir = tmp_vault / "30_Knowledge_Base"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    entity_file = knowledge_dir / "Target.md"

    entity_file.write_text(
        "---\n"
        "entity_type: stock_entity\n"
        "ticker: TGT\n"
        "---\n"
        "I am the target",
        encoding="utf-8",
    )

    related_file = (
        knowledge_dir
        / "Target_Analysis.md"
    )

    related_file.write_text(
        "---\n"
        "entity_type: equity_analysis\n"
        "ticker: TGT\n"
        "date: 2026-08-18\n"
        "---\n"
        "Analysis for target.",
        encoding="utf-8",
    )

    index_file = (
        tmp_vault
        / ".system"
        / "master_index.json"
    )

    index_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    index_file.write_text(
        (
            '{'
            '"version": 1,'
            '"files": ['
            '{"path": "30_Knowledge_Base/Target.md"},'
            '{"path": "30_Knowledge_Base/Target_Analysis.md"}'
            ']'
            '}'
        ),
        encoding="utf-8",
    )

    res = isolated_archivist.search_graph_context.invoke({
        "entity_name": "Target",
    })

    assert "GRAPH CONTEXT: TGT" in res
    assert "Name: Target" in res
    assert "Ticker: TGT" in res
    assert "I am the target" in res
    assert "Analysis for target." in res
    assert "EQUITY ANALYSIS" in res
    assert "Related files: 1" in res

"""Tests for core/model_registry.py — single-model architecture."""

from core.model_registry import (
    FREE_MODEL,
    REGISTRY,
    get_model_name,
    get_registry_summary,
)


def test_registry_has_exactly_14_slots():
    assert len(REGISTRY) == 14


def test_registry_has_10_agent_and_4_tool_slots():
    agent_slots = [s for s in REGISTRY.values() if s.layer == "agent"]
    tool_slots = [s for s in REGISTRY.values() if s.layer == "tool"]

    assert len(agent_slots) == 10
    assert len(tool_slots) == 4


def test_all_expected_slot_keys_present():
    expected = {
        "manager",
        "router",
        "archivist",
        "bookkeeper",
        "macro_quant",
        "economist",
        "allocator",
        "equity_quant",
        "equity_narrative",
        "equity_synthesizer",
        "extractor",
        "youtube_pitch",
        "news_triage",
        "thai_title_translation",
    }

    assert set(REGISTRY.keys()) == expected


def test_free_model_is_nemotron():
    """The project must use the single approved free model."""
    assert FREE_MODEL == "nvidia/nemotron-3-super-120b-a12b:free"


def test_get_model_name_returns_single_approved_model(monkeypatch):
    """Every slot must resolve to the same approved model."""
    monkeypatch.delenv("EXTRACTOR_MODEL", raising=False)

    assert get_model_name("extractor") == FREE_MODEL


def test_get_model_name_ignores_environment_override(monkeypatch):
    """Environment variables must not override the single-model policy."""
    monkeypatch.setenv("EXTRACTOR_MODEL", "claude-opus-5")

    assert get_model_name("extractor") == FREE_MODEL


def test_get_model_name_unknown_slot_raises_keyerror():
    import pytest

    with pytest.raises(KeyError):
        get_model_name("does_not_exist")


def test_all_slots_resolve_to_same_model():
    """All registry slots must resolve to FREE_MODEL."""
    for slot_key in REGISTRY:
        assert get_model_name(slot_key) == FREE_MODEL


def test_registry_defaults_are_all_free_model():
    """Every slot default must equal the approved free model."""
    for slot_key, slot in REGISTRY.items():
        assert slot.default == FREE_MODEL


def test_get_registry_summary_returns_14_entries():
    summary = get_registry_summary()

    assert len(summary) == 14


def test_get_registry_summary_has_no_overrides(monkeypatch):
    """Single-model architecture must never report an override."""
    monkeypatch.setenv(
        "NEWS_FUNNEL_TRIAGE_MODEL",
        "custom-model",
    )

    monkeypatch.setenv(
        "NEWS_FUNNEL_SYNTHESIS_MODEL",
        "another-custom-model",
    )

    summary = {
        row["slot"]: row
        for row in get_registry_summary()
    }

    assert summary["news_triage"]["is_overridden"] is False
    assert summary["news_triage"]["resolved_model"] == FREE_MODEL

    assert summary["thai_title_translation"]["is_overridden"] is False
    assert (
        summary["thai_title_translation"]["resolved_model"]
        == FREE_MODEL
    )


def test_registry_summary_entries_have_all_expected_fields():
    row = get_registry_summary()[0]

    assert set(row.keys()) == {
        "slot",
        "env_var",
        "resolved_model",
        "default",
        "is_overridden",
        "purpose",
        "layer",
    }


def test_registry_summary_all_resolved_models_are_free_model():
    """Every summary entry must resolve to the same approved model."""
    summary = get_registry_summary()

    for row in summary:
        assert row["resolved_model"] == FREE_MODEL
        assert row["default"] == FREE_MODEL
        assert row["is_overridden"] is False

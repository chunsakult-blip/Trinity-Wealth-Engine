"""Centralized LLM model registry.

Single-model architecture:
    NVIDIA Nemotron 3 Super 120B A12B via OpenRouter

Every agent and tool uses the same model.
"""

from dataclasses import dataclass


FREE_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


@dataclass(frozen=True)
class ModelSlot:
    env_var: str
    default: str
    purpose: str
    layer: str  # "agent" | "tool"


REGISTRY: dict[str, ModelSlot] = {
    # --- Agent Layer ---
    "manager": ModelSlot(
        "MANAGER_MODEL",
        FREE_MODEL,
        "Manager Agent โ€” routing and orchestration",
        "agent",
    ),
    "router": ModelSlot(
        "ROUTER_MODEL",
        FREE_MODEL,
        "Structured routing (RouterDecision)",
        "agent",
    ),
    "archivist": ModelSlot(
        "ARCHIVIST_MODEL",
        FREE_MODEL,
        "PKM management agent",
        "agent",
    ),
    "bookkeeper": ModelSlot(
        "BOOKKEEPER_MODEL",
        FREE_MODEL,
        "Portfolio & accounting agent",
        "agent",
    ),
    "macro_quant": ModelSlot(
        "MACRO_QUANT_MODEL",
        FREE_MODEL,
        "Quant Macro Matrix agent",
        "agent",
    ),
    "economist": ModelSlot(
        "MACRO_ECONOMIST_MODEL",
        FREE_MODEL,
        "Macroeconomic narrative synthesis agent",
        "agent",
    ),
    "allocator": ModelSlot(
        "STRATEGIC_ALLOCATOR_MODEL",
        FREE_MODEL,
        "Strategic Allocator agent",
        "agent",
    ),
    "equity_quant": ModelSlot(
        "EQUITY_QUANT_MODEL",
        FREE_MODEL,
        "Equity Quant Signals agent (deterministic)",
        "agent",
    ),
    "equity_narrative": ModelSlot(
        "EQUITY_NARRATIVE_MODEL",
        FREE_MODEL,
        "Equity Sentiment/Narrative synthesis agent",
        "agent",
    ),
    "equity_synthesizer": ModelSlot(
        "EQUITY_SYNTHESIZER_MODEL",
        FREE_MODEL,
        "Equity final report synthesis agent",
        "agent",
    ),

    # --- Tool Layer ---
    "extractor": ModelSlot(
        "EXTRACTOR_MODEL",
        FREE_MODEL,
        "Article/PDF/YouTube content extraction",
        "tool",
    ),

    "youtube_pitch": ModelSlot(
        "YOUTUBE_PITCH_MODEL",
        FREE_MODEL,
        "YouTube investigative pitch and NotebookLM briefing synthesis",
        "tool",
    ),

    "news_triage": ModelSlot(
        "NEWS_FUNNEL_TRIAGE_MODEL",
        FREE_MODEL,
        "News impact scoring (batch triage)",
        "tool",
    ),
    "thai_title_translation": ModelSlot(
        "NEWS_FUNNEL_SYNTHESIS_MODEL",
        FREE_MODEL,
        "Thai title translation for news",
        "tool",
    ),
}


def get_model_name(slot_key: str) -> str:
    """Return the single approved free model."""
    if slot_key not in REGISTRY:
        raise KeyError(f"Unknown model slot: {slot_key}")

    return FREE_MODEL


def get_registry_summary() -> list[dict]:
    """Return all slots with their resolved model."""
    return [
        {
            "slot": key,
            "env_var": slot.env_var,
            "resolved_model": FREE_MODEL,
            "default": FREE_MODEL,
            "is_overridden": False,
            "purpose": slot.purpose,
            "layer": slot.layer,
        }
        for key, slot in REGISTRY.items()
    ]

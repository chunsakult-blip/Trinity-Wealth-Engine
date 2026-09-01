"""Centralized LLM factory.

Single-provider / single-model architecture.

ALL LLM requests are routed through OpenRouter using:\r?\n    nvidia/nemotron-3-super-120b-a12b:free

No Google or Anthropic runtime provider is supported.
"""

import os
from typing import Optional, Any

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableWithFallbacks
from langchain_openai import ChatOpenAI

from core.logger import get_logger
from core.model_registry import FREE_MODEL

# Always load project .env when this module is imported.
load_dotenv()

log = get_logger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Single approved model.
FALLBACK_MODEL = FREE_MODEL


def detect_provider(model_name: str) -> str:
    """Return the only supported provider."""
    return "openrouter"


def _build_primary(
    provider: str,
    model_name: str,
    temperature: float,
    max_output_tokens: Optional[int] = None,
) -> BaseChatModel:
    """Build the single supported LLM implementation."""

    if provider != "openrouter":
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            "Trinity-Wealth-Engine uses OpenRouter only."
        )

    # Hard-lock the model.
    if model_name != FREE_MODEL:
        log.warning(
            "Requested model '%s' was rejected. "
            "Using enforced free model '%s'.",
            model_name,
            FREE_MODEL,
        )
        model_name = FREE_MODEL

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured. "
            "Check the project .env file."
        )

    return ChatOpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        model=FREE_MODEL,
        temperature=temperature,
        max_tokens=max_output_tokens,
        max_retries=5,
        request_timeout=120,
    )


def get_llm(
    provider: str = "openrouter",
    model_name: str = FREE_MODEL,
    temperature: float = 0.0,
    use_fallback: bool = False,
    max_output_tokens: Optional[int] = None,
) -> BaseChatModel | RunnableWithFallbacks:
    """Create the single approved LLM.

    provider and model_name are retained for backwards compatibility,
    but runtime always uses OpenRouter + FREE_MODEL.
    """

    primary = _build_primary(
        provider="openrouter",
        model_name=FREE_MODEL,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )

    # Single-model policy: no alternate model fallback.
    if use_fallback:
        log.info(
            "Fallback requested, but single-model policy is active. "
            "No alternate model will be used."
        )

    return primary


def invoke_structured_llm(
    schema: Any,
    model_env: str,
    prompt_lines: list[str],
    purpose: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
    default_model: str = FREE_MODEL,
    provider: str = "openrouter",
    **kwargs: Any,
) -> Any:
    """Invoke the single approved model with structured output."""

    model_name = FREE_MODEL

    call_purpose = purpose or getattr(
        schema,
        "__name__",
        str(schema),
    )

    log.info(
        "LLM Call | purpose=%s | model=%s | provider=openrouter | max_tokens=%s",
        call_purpose,
        model_name,
        max_output_tokens,
    )

    llm = get_llm(
        provider="openrouter",
        model_name=FREE_MODEL,
        temperature=0.0,
        max_output_tokens=max_output_tokens,
    )

    structured_llm = llm.with_structured_output(schema)

    return structured_llm.invoke(
        "\n".join(prompt_lines)
    )


def _fetch_openrouter_models() -> list[str]:
    """Fetch available OpenRouter models."""

    try:
        import httpx

        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            log.warning("OPENROUTER_API_KEY is not configured.")
            return []

        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        resp = httpx.get(
            f"{OPENROUTER_BASE_URL}/models",
            headers=headers,
            timeout=10,
        )

        resp.raise_for_status()

        return [
            m["id"]
            for m in resp.json().get("data", [])
        ]

    except Exception as e:
        log.warning(
            "OpenRouter models fetch failed: %s",
            e,
        )
        return []


def list_available_models(
    provider: str | None = None,
) -> list[str] | dict[str, list[str]]:
    """Return available OpenRouter models."""

    if provider not in (None, "openrouter"):
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            "Only 'openrouter' is supported."
        )

    models = _fetch_openrouter_models()

    if provider == "openrouter":
        return models

    return {
        "openrouter": models,
    }


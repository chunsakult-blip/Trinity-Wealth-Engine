import pytest
from unittest.mock import patch, MagicMock

from langchain_openai import ChatOpenAI

from core.llm_factory import (
    detect_provider,
    _build_primary,
    get_llm,
    _fetch_openrouter_models,
    list_available_models,
)

from core.model_registry import FREE_MODEL


def test_detect_provider():
    """Only OpenRouter is supported."""
    assert detect_provider(FREE_MODEL) == "openrouter"
    assert detect_provider("openai/gpt-4") == "openrouter"
    assert detect_provider("gemini-pro") == "openrouter"
    assert detect_provider("claude-sonnet") == "openrouter"
    assert detect_provider("unknown-model") == "openrouter"


def test_build_primary_openrouter(monkeypatch):
    """Build the single approved OpenRouter model."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    llm = _build_primary(
        "openrouter",
        FREE_MODEL,
        0.0,
    )

    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == FREE_MODEL


def test_build_primary_rejects_non_openrouter():
    """Non-OpenRouter providers are forbidden."""
    with pytest.raises(ValueError, match="OpenRouter only"):
        _build_primary(
            "google",
            "gemini-pro",
            0.0,
        )

    with pytest.raises(ValueError, match="OpenRouter only"):
        _build_primary(
            "anthropic",
            "claude-sonnet",
            0.0,
        )


def test_build_primary_requires_api_key(monkeypatch):
    """OPENROUTER_API_KEY must be configured."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(
        RuntimeError,
        match="OPENROUTER_API_KEY is not configured",
    ):
        _build_primary(
            "openrouter",
            FREE_MODEL,
            0.0,
        )


def test_build_primary_hard_locks_model(monkeypatch):
    """Any requested model must resolve to FREE_MODEL."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    llm = _build_primary(
        "openrouter",
        "some/other-model",
        0.0,
    )

    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == FREE_MODEL


def test_get_llm_single_model(monkeypatch):
    """get_llm always returns the single approved model."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    llm = get_llm(
        provider="google",
        model_name="gemini-pro",
    )

    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == FREE_MODEL


def test_get_llm_ignores_fallback(monkeypatch):
    """Fallback requests must not create an alternate model."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    with patch("core.llm_factory._build_primary") as mock_build:
        mock_primary = MagicMock()
        mock_build.return_value = mock_primary

        result = get_llm(
            provider="openrouter",
            model_name=FREE_MODEL,
            use_fallback=True,
        )

        assert result == mock_primary
        assert mock_build.call_count == 1


def test_fetch_openrouter_models(monkeypatch):
    """Fetch available models from OpenRouter."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [
            {"id": "model-a"},
            {"id": "model-b"},
        ]
    }

    with patch("httpx.get", return_value=mock_resp):
        result = _fetch_openrouter_models()

    assert result == ["model-a", "model-b"]


def test_fetch_openrouter_models_failure(monkeypatch):
    """OpenRouter model discovery failures return an empty list."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    with patch(
        "httpx.get",
        side_effect=Exception("Network error"),
    ):
        result = _fetch_openrouter_models()

    assert result == []


def test_fetch_openrouter_models_without_api_key(monkeypatch):
    """Model discovery without an API key returns an empty list."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = _fetch_openrouter_models()

    assert result == []


def test_list_available_models_openrouter(monkeypatch):
    """Only OpenRouter model listing is supported."""
    with patch(
        "core.llm_factory._fetch_openrouter_models",
        return_value=["model-a", "model-b"],
    ):
        result = list_available_models("openrouter")

    assert result == ["model-a", "model-b"]


def test_list_available_models_none(monkeypatch):
    """Default listing returns only OpenRouter."""
    with patch(
        "core.llm_factory._fetch_openrouter_models",
        return_value=["model-a", "model-b"],
    ):
        result = list_available_models(None)

    assert result == {
        "openrouter": ["model-a", "model-b"],
    }


def test_list_available_models_rejects_other_providers():
    """Google and Anthropic are no longer supported."""
    with pytest.raises(ValueError):
        list_available_models("google")

    with pytest.raises(ValueError):
        list_available_models("anthropic")

    with pytest.raises(ValueError):
        list_available_models("invalid")


def test_model_registry_is_single_model():
    """All registry slots must resolve to the same approved model."""
    from core.model_registry import REGISTRY

    assert len(REGISTRY) == 14

    for slot_key, slot in REGISTRY.items():
        assert slot.default == FREE_MODEL

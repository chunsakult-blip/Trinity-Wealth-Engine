from types import SimpleNamespace

import pytest

from ai.nick.nick import Nick, NickLLMOutput
import ai.nick.nick as nick_module


def _valid_response():
    return SimpleNamespace(
        content="""{
          "decision": "HOLD",
          "thesis": "Strong business with elevated expectations.",
          "bull_case": "AI demand remains strong.",
          "base_case": "Growth moderates but remains healthy.",
          "bear_case": "AI spending slows materially.",
          "key_risks": ["Valuation", "Cyclicality"],
          "valuation_view": "Premium valuation reflects strong growth.",
          "position_sizing": "Moderate position size.",
          "confidence": 0.75,
          "invalidation_conditions": ["Growth collapses"],
          "positions": [],
          "notes": "Deterministic hardening test."
        }"""
    )


def test_nick_retries_transient_provider_failure(monkeypatch):
    calls = {"count": 0}

    class FakeLLM:
        def invoke(self, prompt):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("502 upstream service error")
            return _valid_response()

    monkeypatch.setattr(nick_module, "get_llm", lambda **kwargs: FakeLLM())
    monkeypatch.setattr("time.sleep", lambda _: None)

    output = Nick()._invoke_llm({})

    assert isinstance(output, NickLLMOutput)
    assert output.decision == "HOLD"
    assert calls["count"] == 2


def test_nick_retries_malformed_json(monkeypatch):
    calls = {"count": 0}

    class FakeLLM:
        def invoke(self, prompt):
            calls["count"] += 1
            if calls["count"] == 1:
                return SimpleNamespace(
                    content='{"decision":"HOLD","thesis":"truncated'
                )
            return _valid_response()

    monkeypatch.setattr(nick_module, "get_llm", lambda **kwargs: FakeLLM())
    monkeypatch.setattr("time.sleep", lambda _: None)

    output = Nick()._invoke_llm({})

    assert isinstance(output, NickLLMOutput)
    assert output.decision == "HOLD"
    assert calls["count"] == 2


def test_nick_retries_schema_validation_failure(monkeypatch):
    calls = {"count": 0}

    class FakeLLM:
        def invoke(self, prompt):
            calls["count"] += 1

            if calls["count"] == 1:
                return SimpleNamespace(
                    content="""{
                      "decision": "HOLD",
                      "thesis": "Test",
                      "bull_case": "Test",
                      "base_case": "Test",
                      "bear_case": "Test",
                      "key_risks": "not-a-list",
                      "confidence": 0.7,
                      "positions": []
                    }"""
                )

            return _valid_response()

    monkeypatch.setattr(nick_module, "get_llm", lambda **kwargs: FakeLLM())
    monkeypatch.setattr("time.sleep", lambda _: None)

    output = Nick()._invoke_llm({})

    assert isinstance(output, NickLLMOutput)
    assert output.decision == "HOLD"
    assert calls["count"] == 2


def test_nick_fails_after_retry_budget_is_exhausted(monkeypatch):
    calls = {"count": 0}

    class FakeLLM:
        def invoke(self, prompt):
            calls["count"] += 1
            return SimpleNamespace(
                content='{"decision":"HOLD","thesis":"truncated'
            )

    monkeypatch.setattr(nick_module, "get_llm", lambda **kwargs: FakeLLM())
    monkeypatch.setattr("time.sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="failed after 3 attempt"):
        Nick()._invoke_llm({})

    assert calls["count"] == 3

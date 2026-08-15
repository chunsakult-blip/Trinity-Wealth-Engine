"""
Trinity -> AI Intelligence integration boundary.

This module deliberately keeps the existing Trinity execution engine
independent from the higher-level AI intelligence layer.

The adapter converts Trinity outputs into the shared AgentResult
contract used by the AI layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ai.agent_result import AgentResult
from ai.research.request import ResearchRequest


class TrinityAdapter:
    """
    Boundary adapter between the existing Trinity engine and Trinity v2 AI.

    Design goals:
    - Never mutate the original Trinity result.
    - Accept both dictionaries and AgentResult objects.
    - Normalize common Trinity equity-analysis fields.
    - Preserve the original payload under data["trinity_output"].
    - Keep evidence structured whenever possible.
    """

    name = "Trinity Adapter"

    def research_request(
        self,
        query: str,
        tickers: list[str] | None = None,
        research_type: str = "company",
        depth: str = "standard",
    ) -> ResearchRequest:
        """Create a normalized research request for the AI research layer."""
        normalized_tickers = [
            str(t).strip().upper()
            for t in (tickers or [])
            if str(t).strip()
        ]

        return ResearchRequest(
            query=query.strip(),
            tickers=normalized_tickers,
            research_type=research_type.strip() or "company",
            depth=depth.strip() or "standard",
        )

    def adapt(
        self,
        trinity_output: Any,
        *,
        agent: str = "Trinity",
        query: str = "",
        tickers: list[str] | None = None,
    ) -> AgentResult:
        """
        Convert a Trinity result into the common AgentResult contract.

        The adapter is intentionally permissive at this stage because
        Trinity currently has several output paths.
        """

        if isinstance(trinity_output, AgentResult):
            return AgentResult(
                agent=trinity_output.agent,
                status=trinity_output.status,
                summary=trinity_output.summary,
                data=dict(trinity_output.data),
                evidence=list(trinity_output.evidence),
                warnings=list(trinity_output.warnings),
                confidence=trinity_output.confidence,
            )

        payload = self._to_mapping(trinity_output)

        normalized_tickers = self._normalize_tickers(
            tickers or payload.get("tickers") or payload.get("ticker")
        )

        status = self._normalize_status(payload)
        summary = self._extract_summary(payload, trinity_output)

        evidence = self._extract_evidence(payload)
        warnings = self._extract_warnings(payload)

        data = {
            "query": query,
            "tickers": normalized_tickers,
            "trinity_output": trinity_output,
            "normalized": self._normalize_payload(payload),
        }

        confidence = self._extract_confidence(payload)

        return AgentResult(
            agent=agent,
            status=status,
            summary=summary,
            data=data,
            evidence=evidence,
            warnings=warnings,
            confidence=confidence,
        )

    @staticmethod
    def _to_mapping(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)

        if hasattr(value, "model_dump"):
            try:
                dumped = value.model_dump(mode="json")
                if isinstance(dumped, Mapping):
                    return dict(dumped)
            except Exception:
                pass

        if hasattr(value, "__dict__"):
            try:
                return dict(vars(value))
            except Exception:
                pass

        return {"value": value}

    @staticmethod
    def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        """
        Preserve useful top-level fields without making assumptions about
        the exact Trinity schema.
        """
        result: dict[str, Any] = {}

        for key, value in payload.items():
            if key.startswith("_"):
                continue

            if key in {
                "ticker",
                "tickers",
                "market",
                "company_name",
                "analysis_date",
                "quant_signals",
                "sentiment_context",
                "narrative_analysis",
                "base_case_summary",
                "status",
                "summary",
                "confidence",
                "warnings",
                "evidence",
                "sources",
                "report",
            }:
                result[key] = value

        return result

    @staticmethod
    def _normalize_tickers(value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            values = [value]
        elif isinstance(value, (list, tuple, set)):
            values = list(value)
        else:
            values = [value]

        result: list[str] = []

        for item in values:
            ticker = str(item).strip().upper()

            if ticker and ticker not in result:
                result.append(ticker)

        return result

    @staticmethod
    def _normalize_status(payload: Mapping[str, Any]) -> str:
        raw = str(payload.get("status", "")).strip().lower()

        if raw in {"success", "completed", "complete", "ok"}:
            return "success"

        if raw in {"error", "failed", "failure"}:
            return "failure"

        return "success"

    @staticmethod
    def _extract_summary(
        payload: Mapping[str, Any],
        original: Any,
    ) -> str:
        for key in (
            "summary",
            "base_case_summary",
            "narrative_analysis",
            "report",
        ):
            value = payload.get(key)

            if value is not None:
                text = str(value).strip()

                if text:
                    return text

        if isinstance(original, str):
            return original.strip()

        return "Trinity analysis successfully adapted into the AI intelligence layer."

    @staticmethod
    def _extract_evidence(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        raw = payload.get("evidence")

        if raw is None:
            raw = payload.get("sources")

        if raw is None:
            return []

        if isinstance(raw, Mapping):
            return [dict(raw)]

        if isinstance(raw, (list, tuple)):
            result: list[dict[str, Any]] = []

            for item in raw:
                if isinstance(item, Mapping):
                    result.append(dict(item))
                else:
                    result.append({"source": str(item)})

            return result

        return [{"source": str(raw)}]

    @staticmethod
    def _extract_warnings(payload: Mapping[str, Any]) -> list[str]:
        raw = payload.get("warnings")

        if raw is None:
            return []

        if isinstance(raw, str):
            return [raw] if raw.strip() else []

        if isinstance(raw, (list, tuple)):
            return [
                str(item).strip()
                for item in raw
                if str(item).strip()
            ]

        return [str(raw)]

    @staticmethod
    def _extract_confidence(payload: Mapping[str, Any]) -> float | None:
        raw = payload.get("confidence")

        if raw is None:
            return None

        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None

        # Keep the AgentResult contract safe.
        return max(0.0, min(1.0, value))


DEFAULT_TRINITY_ADAPTER = TrinityAdapter()

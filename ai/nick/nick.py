"""
Nick - Chief Investment Officer.

Final investment reasoning boundary.

Nick receives the completed intelligence package and uses the
approved LLM to produce the final investment decision.

Nick must remain blind to the user's real portfolio / holdings.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from ai.nick.blind_gate import NickBlindGate
from ai.nick.decision_contract import (
    NickDecisionContract,
    NickKillCondition,
    NickPositionDecision,
)
from core.llm_factory import detect_provider, get_llm
from core.model_registry import FREE_MODEL


class NickLLMOutput(BaseModel):
    decision: str = Field(
        description=(
            "Final investment decision: BUY, HOLD, TRIM, SELL, or NO_TRADE."
        )
    )

    thesis: str = Field(
        description="Core investment thesis supported by the supplied evidence."
    )

    bull_case: str = Field(
        description="Most credible bullish scenario."
    )

    base_case: str = Field(
        description="Most likely scenario."
    )

    bear_case: str = Field(
        description="Most credible bearish scenario."
    )

    key_risks: list[str] = Field(
        default_factory=list,
        description="Material risks to the thesis."
    )

    valuation_view: str = Field(
        description=(
            "Assessment of valuation versus fundamentals and expectations."
        )
    )

    position_sizing: str = Field(
        description="Recommended position sizing rationale."
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Decision confidence from 0 to 1."
    )

    invalidation_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that invalidate the thesis."
    )

    positions: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Position recommendations. Each item may contain "
            "symbol, thesis, catalyst, kill_conditions, target_weight, "
            "conviction, and status."
        ),
    )

    notes: str = ""


class Nick:
    name = "Nick"
    role = "Chief Investment Officer"

    REQUIRED_DECISION_OUTPUTS = [
        "decision",
        "thesis",
        "bull_case",
        "base_case",
        "bear_case",
        "key_risks",
        "valuation_view",
        "position_sizing",
        "confidence",
        "invalidation_conditions",
    ]

    VALID_TRIGGERS = {
        "nick-init",
        "nick-weekly",
        "nick-quarterly",
    }

    def __init__(self) -> None:
        self.blind_gate = NickBlindGate()
        self.model_name = FREE_MODEL

    def evaluate(
        self,
        investment_package: dict[str, Any],
    ) -> dict[str, Any]:

        package = dict(investment_package or {})
        warnings: list[str] = []

        required_stages = {
            "research": package.get("research"),
            "financial": package.get("financial"),
            "investment": package.get("investment"),
            "verification": package.get("verification"),
            "challenge": package.get("challenge"),
            "reflection": package.get("reflection"),
        }

        for name, result in required_stages.items():

            if result is None:
                warnings.append(
                    f"{name.title()} stage has not completed."
                )
                continue

            status = (
                result.get("status")
                if isinstance(result, dict)
                else getattr(result, "status", None)
            )

            if status in {"failure", "error"}:
                warnings.append(
                    f"{name.title()} stage failed."
                )

        if warnings:
            return {
                "agent": self.name,
                "role": self.role,
                "status": "incomplete",
                "decision": None,
                "investment_package": package,
                "warnings": warnings,
                "decision_contract": {
                    "required_outputs": list(
                        self.REQUIRED_DECISION_OUTPUTS
                    )
                },
            }

        try:

            safe_package = self._prepare_safe_package(package)

            output = self._invoke_llm(safe_package)

            contract = self._build_decision_contract(
                output,
                package,
            )

            contract.validate()

            return {
                "agent": self.name,
                "role": self.role,
                "status": "ready",
                "decision": output.decision,
                "thesis": output.thesis,
                "bull_case": output.bull_case,
                "base_case": output.base_case,
                "bear_case": output.bear_case,
                "key_risks": output.key_risks,
                "valuation_view": output.valuation_view,
                "position_sizing": output.position_sizing,
                "confidence": output.confidence,
                "invalidation_conditions": (
                    output.invalidation_conditions
                ),
                "positions": [
                    position.to_dict()
                    for position in contract.positions
                ],
                "contract": contract.to_dict(),
                "investment_package": package,
                "warnings": [],
                "decision_contract": {
                    "required_outputs": list(
                        self.REQUIRED_DECISION_OUTPUTS
                    )
                },
            }

        except Exception as exc:

            import traceback

            print(
                "\n" + "=" * 100,
                flush=True,
            )
            print(
                "NICK INTERNAL EXCEPTION",
                flush=True,
            )
            print(
                "=" * 100,
                flush=True,
            )
            print(
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            traceback.print_exc()
            print(
                "=" * 100 + "\n",
                flush=True,
            )

            return {
                "agent": self.name,
                "role": self.role,
                "status": "error",
                "decision": None,
                "investment_package": package,
                "warnings": [
                    f"Nick LLM decision failed: {exc}"
                ],
                "decision_contract": {
                    "required_outputs": list(
                        self.REQUIRED_DECISION_OUTPUTS
                    )
                },
            }

    def _prepare_safe_package(
        self,
        package: dict[str, Any],
    ) -> dict[str, Any]:

        def sanitize(
            value: Any,
            path: str = "",
        ) -> Any:

            if isinstance(value, dict):

                result: dict[str, Any] = {}

                for key, item in value.items():

                    key_path = (
                        f"{path}/{key}"
                        if path
                        else str(key)
                    )

                    if not self.blind_gate.is_allowed_input(
                        key_path
                    ):
                        continue

                    result[key] = sanitize(
                        item,
                        key_path,
                    )

                return result

            if isinstance(value, list):

                return [
                    sanitize(
                        item,
                        f"{path}/item",
                    )
                    for item in value
                ]

            return value

        return sanitize(package)

    def _invoke_llm(
        self,
        package: dict[str, Any],
    ) -> NickLLMOutput:

        provider = detect_provider(self.model_name)

        llm = get_llm(
            provider=provider,
            model_name=self.model_name,
            temperature=0.0,
            use_fallback=False,
            max_output_tokens=6000,
        )

        prompt = self._build_prompt(package)

        fallback_prompt = prompt + """

OUTPUT FORMAT REQUIREMENT:

Return ONLY one valid JSON object.

Do NOT use markdown.
Do NOT use ```json fences.
Do NOT add explanations before or after the JSON.

The JSON object MUST contain exactly these required fields:

{
  "decision": "BUY|HOLD|TRIM|SELL|NO_TRADE",
  "thesis": "...",
  "bull_case": "...",
  "base_case": "...",
  "bear_case": "...",
  "key_risks": ["..."],
  "valuation_view": "...",
  "position_sizing": "...",
  "confidence": 0.0,
  "invalidation_conditions": ["..."],
  "positions": [],
  "notes": "..."
}

Important:
- decision MUST be one of BUY, HOLD, TRIM, SELL, NO_TRADE.
- confidence MUST be a number between 0 and 1.
- positions MUST be a JSON array.
- key_risks MUST be a JSON array.
- invalidation_conditions MUST be a JSON array.
- Do not invent information not contained in the intelligence package.
"""

        print("[NICK] LLM START", flush=True)

        import time
        _nick_t = time.perf_counter()

        max_attempts = 3
        retry_delays = (0.5, 1.0)
        response = None
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = llm.invoke(fallback_prompt)
                break

            except Exception as exc:
                last_exc = exc
                elapsed = time.perf_counter() - _nick_t
                message = str(exc).lower()

                transient = any(
                    token in message
                    for token in (
                        "502",
                        "503",
                        "429",
                        "temporarily overloaded",
                        "service unavailable",
                        "rate limit",
                    )
                )

                print(
                    f"[NICK] LLM FAILED attempt={attempt}/{max_attempts} "
                    f"{elapsed:.1f}s: {type(exc).__name__}: {exc}",
                    flush=True,
                )

                if not transient or attempt >= max_attempts:
                    raise RuntimeError(
                        f"Nick LLM provider failed: {exc}"
                    ) from exc

                time.sleep(retry_delays[attempt - 1])

        if response is None:
            raise RuntimeError(
                f"Nick LLM provider failed: {last_exc}"
            ) from last_exc

        print(
            f"[NICK] LLM DONE "
            f"{time.perf_counter()-_nick_t:.1f}s",
            flush=True,
        )

        content = getattr(response, "content", None)

        if not content:
            raise RuntimeError(
                "Nick LLM returned empty content."
            )

        if isinstance(content, list):

            parts = []

            for item in content:

                if isinstance(item, str):
                    parts.append(item)

                elif isinstance(item, dict):
                    value = item.get("text")

                    if value:
                        parts.append(str(value))

            content = "".join(parts)

        content = str(content).strip()

        if content.startswith("```"):

            lines = content.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            content = "\n".join(lines).strip()

        try:

            data = json.loads(content)

        except json.JSONDecodeError:

            start_json = content.find("{")
            end_json = content.rfind("}")

            if (
                start_json == -1
                or end_json == -1
                or end_json <= start_json
            ):
                raise RuntimeError(
                    "Nick LLM response did not contain "
                    "a valid JSON object. "
                    f"Raw response: {content[:1000]}"
                )

            try:
                data = json.loads(
                    content[start_json:end_json + 1]
                )

            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Nick LLM returned malformed JSON. "
                    f"Raw response: {content[:1000]}"
                ) from exc

        try:
            return NickLLMOutput.model_validate(data)

        except Exception as exc:
            raise RuntimeError(
                "Nick LLM JSON failed schema validation. "
                f"Validation error: {exc}"
            ) from exc


    def _build_prompt(
        self,
        package: dict[str, Any],
    ) -> str:

        payload = json.dumps(
            package,
            ensure_ascii=False,
            default=str,
        )

        return f"""
You are Nick, the Chief Investment Officer of an AI investment
research system.

You are the FINAL investment reasoning boundary.

Your task is to synthesize the completed intelligence package
into a disciplined investment decision.

RULES:

1. Use ONLY information contained in the supplied package.
2. NEVER invent financial data, prices, valuation metrics,
   growth rates, catalysts, risks, or market facts.
3. If evidence is insufficient or materially conflicting,
   prefer NO_TRADE.
4. Explicitly evaluate bull, base, and bear cases.
5. Evaluate valuation, fundamentals, risks, and uncertainty.
6. Position sizing must reflect conviction and risk.
7. Every position must contain a thesis and catalyst.
8. Add measurable kill conditions whenever possible.
9. Do NOT use or infer the user's real portfolio.
10. Do NOT use actual holdings, personal position sizes,
    transaction history, or diary information.
11. Do not fabricate missing information.
12. The final decision must NOT be PENDING_LLM_DECISION.
13. Preserve capital when uncertainty is high.

VALID DECISIONS:

BUY
HOLD
TRIM
SELL
NO_TRADE

The final output must be a genuine CIO-level investment decision.

INTELLIGENCE PACKAGE:

{payload}
""".strip()

    def _build_decision_contract(
        self,
        output: NickLLMOutput,
        package: dict[str, Any],
    ) -> NickDecisionContract:

        request = package.get("request")

        trigger = "nick-init"

        if isinstance(request, dict):

            candidate = str(
                request.get("trigger")
                or request.get("mode")
                or ""
            ).strip()

            if candidate in self.VALID_TRIGGERS:
                trigger = candidate

        positions: list[NickPositionDecision] = []

        for raw in output.positions:

            if not isinstance(raw, dict):
                continue

            symbol = str(
                raw.get("symbol")
                or raw.get("ticker")
                or ""
            ).strip().upper()

            if not symbol:
                continue

            kill_conditions: list[NickKillCondition] = []

            raw_kills = raw.get(
                "kill_conditions",
                [],
            )

            if isinstance(raw_kills, list):

                for item in raw_kills:

                    if not isinstance(item, dict):
                        continue

                    metric = str(
                        item.get("metric") or ""
                    ).strip()

                    trigger_text = str(
                        item.get("trigger") or ""
                    ).strip()

                    if metric and trigger_text:

                        kill_conditions.append(
                            NickKillCondition(
                                metric=metric,
                                trigger=trigger_text,
                                action=str(
                                    item.get(
                                        "action",
                                        "reduce_or_exit",
                                    )
                                ),
                            )
                        )

            status = str(
                raw.get(
                    "status",
                    "intact",
                )
            ).strip().lower()

            if status not in {
                "intact",
                "evolving",
                "invalidated",
                "no_trade",
            }:
                status = "intact"

            try:

                target_weight = float(
                    raw.get(
                        "target_weight",
                        0.0,
                    )
                )

            except (TypeError, ValueError):

                target_weight = 0.0

            try:

                conviction = float(
                    raw.get(
                        "conviction",
                        output.confidence,
                    )
                )

            except (TypeError, ValueError):

                conviction = output.confidence

            target_weight = max(
                0.0,
                min(1.0, target_weight),
            )

            conviction = max(
                0.0,
                min(1.0, conviction),
            )

            positions.append(
                NickPositionDecision(
                    symbol=symbol,
                    thesis=str(
                        raw.get(
                            "thesis",
                            output.thesis,
                        )
                    ),
                    catalyst=str(
                        raw.get(
                            "catalyst",
                            "",
                        )
                    ),
                    kill_conditions=kill_conditions,
                    target_weight=target_weight,
                    conviction=conviction,
                    status=status,
                )
            )

        return NickDecisionContract(
            trigger=trigger,
            benchmark="SPY",
            cash_weight=0.2,
            positions=positions,
            notes=output.notes,
        )

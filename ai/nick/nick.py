"""
Nick - Chief Investment Officer.

Final reasoning boundary. The deterministic implementation
does not invent an investment decision. It validates that the
intelligence package is complete and prepares the LLM contract.
"""

from __future__ import annotations

from typing import Any


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

    def evaluate(
        self,
        investment_package: dict[str, Any],
    ) -> dict[str, Any]:

        package = dict(investment_package or {})

        required_stages = {
            "research": package.get("research"),
            "verification": package.get("verification"),
            "challenge": package.get("challenge"),
            "reflection": package.get("reflection"),
        }

        warnings: list[str] = []

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
            status = "incomplete"
            decision = None
        else:
            status = "ready"
            decision = "PENDING_LLM_DECISION"

        return {
            "agent": self.name,
            "role": self.role,
            "status": status,
            "decision": decision,
            "investment_package": package,
            "warnings": warnings,
            "decision_contract": {
                "required_outputs": list(
                    self.REQUIRED_DECISION_OUTPUTS
                )
            },
        }

"""
Trinity Chief Agent.

The Chief coordinates investment intelligence.
It does NOT directly perform every research task.

Nick remains the final investment decision layer.
"""

from ai.agent_result import AgentResult


class ChiefAgent:

    name = "Trinity Chief"

    def __init__(self) -> None:
        self.state = "ready"

    def plan(self, user_request: str) -> AgentResult:
        return AgentResult(
            agent=self.name,
            status="success",
            summary="Investment request accepted by Chief Agent.",
            data={
                "request": user_request,
                "next_stage": "research_orchestration",
            },
        )

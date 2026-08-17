"""
ATLAS -> Trinity execution bridge.

This module executes the existing Trinity Manager graph and returns
a normalized mapping suitable for TrinityAdapter.

Important:
- Does not modify the existing Trinity graph.
- Does not replace api/jobs.py.
- Uses the same graph construction path as the production job runner.
- Collects LangGraph stream updates into a final state snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.manager_agent import build_graph


class TrinityRunner:
    """
    Execute the existing Trinity Manager graph from the ATLAS layer.
    """

    name = "Trinity Runner"

    def __init__(self, checkpointer: Any = None) -> None:
        self.checkpointer = checkpointer

    def run(
        self,
        *,
        instruction: str,
        thread_id: str,
        recursion_limit: int = 40,
    ) -> dict[str, Any]:
        """
        Execute the Trinity manager graph and collect its final state.

        The existing Trinity graph uses graph.stream(..., stream_mode="updates"),
        so this bridge intentionally follows that execution contract.
        """

        graph = build_graph(checkpointer=self.checkpointer)

        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": recursion_limit,
            "tags": [
                "atlas",
                "intelligence",
                "trinity-bridge",
            ],
            "metadata": {
                "run_type": "atlas_intelligence",
                "thread_id": thread_id,
            },
        }

        final_state: dict[str, Any] = {}
        events: list[dict[str, Any]] = []

        stream_input = {
            "messages": [
                ("user", instruction),
            ]
        }

        for event in graph.stream(
            stream_input,
            config=config,
            stream_mode="updates",
        ):
            if not isinstance(event, Mapping):
                continue

            event_dict = dict(event)
            events.append(event_dict)

            self._merge_update(
                final_state,
                event_dict,
            )

        return {
            "status": "success",
            "thread_id": thread_id,
            "state": final_state,
            "events": events,
        }

    @staticmethod
    def _merge_update(
        target: dict[str, Any],
        event: Mapping[str, Any],
    ) -> None:
        """
        Merge LangGraph update events into a final state snapshot.

        Nested node updates are flattened one level so the resulting
        structure remains easy for TrinityAdapter to inspect.
        """

        for node_name, node_update in event.items():

            if isinstance(node_update, Mapping):
                existing = target.get(node_name)

                if isinstance(existing, dict):
                    existing.update(dict(node_update))
                else:
                    target[node_name] = dict(node_update)

                # Also expose common state keys at the top level.
                for key, value in node_update.items():
                    target[key] = value

            else:
                target[node_name] = node_update


DEFAULT_TRINITY_RUNNER = TrinityRunner()

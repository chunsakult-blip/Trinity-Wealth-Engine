import os
import uuid

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

from core.logger import setup_logging
from core.retry import is_transient_error as _is_transient_error, with_retry
from core.security import anonymize_pii
from core.utils import normalize_content

load_dotenv()
setup_logging()

from langchain_core.messages import HumanMessage, AIMessage


def _display(node_name: str, state: dict) -> None:
    messages = state.get("messages") if isinstance(state, dict) else None
    if not messages:
        return

    last = messages[-1] if isinstance(messages, list) else messages

    # ข้าม HumanMessage(name="manager") ที่เป็น internal instruction
    if isinstance(last, HumanMessage) and getattr(last, "name", None) == "manager":
        return

    content = normalize_content(getattr(last, "content", ""))
    if not content:
        return

    if isinstance(last, AIMessage):
        sender = node_name.replace("post_", "").capitalize()
        print(f"\n[{sender}]: {content}")


def _run_turn(graph, inputs: dict, config: dict) -> None:
    for event in graph.stream(inputs, config=config, stream_mode="updates"):
        for node_name, state in event.items():
            if not isinstance(state, dict) or "messages" not in state:
                continue
            _display(node_name, state)


def main():
    # Trinity-Wealth-Engine uses a single LLM provider:
    # OpenRouter -> NVIDIA Nemotron 3 Super 120B A12B :free
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("ERROR: กรุณาตั้งค่า OPENROUTER_API_KEY ใน .env ก่อน")
        return

    from agents.manager_agent import build_graph
    from tools.archivist.core import init_vault_structure

    init_vault_structure()

    print("=" * 60)
    print("  Trinity-Wealth-Engine — Multi-Agent Investment System")
    print("  LLM: NVIDIA Nemotron 3 Super 120B A12B via OpenRouter")
    print("  Provider: OpenRouter")
    print("  พิมพ์ 'quit' 'exit' หรือ 'ออก' เพื่อออกจากโปรแกรม")
    print("=" * 60)

    checkpoint_path = os.getenv(
        "CHECKPOINT_DB_PATH",
        "data/checkpoints.sqlite",
    )

    os.makedirs(
        os.path.dirname(checkpoint_path) or ".",
        exist_ok=True,
    )

    with SqliteSaver.from_conn_string(checkpoint_path) as memory:
        graph = build_graph(checkpointer=memory)

        config = {
            "configurable": {
                "thread_id": str(uuid.uuid4()),
            },
            "recursion_limit": 40,
            "tags": [
                "trinity-wealth-engine",
                "invest-agents",
                "cli-session",
            ],
            "metadata": {
                "run_type": "chain",
                "session_source": "terminal",
            },
        }

        while True:
            try:
                user_input = input("\nคุณ: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nออกจากโปรแกรม...")
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q", "ออก"):
                print("ออกจากโปรแกรม...")
                break

            user_input, had_pii = anonymize_pii(user_input)

            if had_pii:
                print(
                    "[Security] ตรวจพบและลบข้อมูล PII "
                    "ก่อนส่งเข้าประมวลผล"
                )

            print("\n[กำลังประมวลผล...]")

            inputs = {
                "messages": [
                    ("user", user_input),
                ],
            }

            try:
                with_retry(
                    _run_turn,
                    graph,
                    inputs,
                    config,
                )
            except Exception as e:
                if _is_transient_error(e):
                    print(
                        f"\n[System]: ไม่สามารถติดต่อ AI "
                        f"ได้ในขณะนี้ ({type(e).__name__}) "
                        "โปรดลองพิมพ์คำถามของคุณใหม่อีกครั้ง"
                    )
                else:
                    print(f"\nERROR: {e}")


if __name__ == "__main__":
    main()

from langchain_core.language_models.chat_models import BaseChatModel
from langchain.agents import create_agent
from tools.market.equity_quant_tool import compute_equity_quant_signals
from core.prompt_harness import get_harness

# EQUITY_QUANT_SYSTEM_PROMPT ถูกย้ายไปที่ prompts/skills/equity_quant/SKILL.md ผ่านระบบ PromptHarness

_equity_quant_tools = [compute_equity_quant_signals]

def create_equity_quant(model: BaseChatModel):
    return create_agent(
        model=model,
        tools=_equity_quant_tools,
        system_prompt=get_harness("equity_quant").get_system_prompt()
    )

from langchain_core.language_models.chat_models import BaseChatModel
from core.prompt_harness import get_harness


def create_equity_narrative(model: BaseChatModel):
    """Create equity narrative using native tool calling for structured output."""
    from langchain_core.runnables import RunnableLambda
    from langchain_core.messages import AIMessage
    from schemas.micro_quant_schemas import EquitySentimentContext
    from tools.archivist.search import search_all_memories
    from tools.market.news import ingest_stock_news

    def _run_equity_narrative(input_dict):
        ticker = input_dict.get("ticker") or ""
        market = input_dict.get("market", "US")
        company_name = input_dict.get("company_name")

        search_keyword = (
            f"{ticker} {company_name}".strip()
            if company_name
            else ticker
        )

        try:
            vault_text = search_all_memories.invoke(
                {"keyword": search_keyword}
            )
        except Exception as e:
            vault_text = f"Error searching vault: {e}"

        try:
            news_text = ingest_stock_news.invoke(
                {"ticker": ticker, "market": market}
            )
        except Exception as e:
            news_text = f"Error fetching news: {e}"

        context = (
            "=== Vault Sentiment History ===\n"
            f"{vault_text}\n\n"
            "=== Latest News ===\n"
            f"{news_text}"
        )

        structured = model.bind_tools(
            [EquitySentimentContext],
            tool_choice={
                "type": "function",
                "function": {
                    "name": "EquitySentimentContext"
                },
            },
            parallel_tool_calls=False,
        )

        harness = get_harness("equity_narrative")

        res = structured.invoke(
            [
                {
                    "role": "system",
                    "content": harness.get_system_prompt(),
                },
                {
                    "role": "user",
                    "content": harness.get_skill_text(
                        "HUMAN.md",
                        ticker=ticker,
                        context=context,
                    ),
                },
            ]
        )

        if not res.tool_calls:
            raise ValueError(
                "Equity narrative LLM did not return "
                "an EquitySentimentContext tool call"
            )

        parsed = EquitySentimentContext.model_validate(
            res.tool_calls[0]["args"]
        )

        return {
            "messages": [
                AIMessage(
                    content=parsed.model_dump_json(),
                    name="equity_narrative",
                )
            ],
            "equity_news_raw": news_text,
        }

    return RunnableLambda(_run_equity_narrative)
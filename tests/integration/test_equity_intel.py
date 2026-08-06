"""Mock Harness สำหรับ equity_intel pipeline (equity_quant -> equity_narrative -> equity_synthesizer
-> post_equity_intel -> prepare_archivist) — มิเรอร์ tests/integration/test_macro.py::test_macro_analysis_flow_mocked_router
"""
from unittest.mock import patch, MagicMock

from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage

from agents.manager_agent import build_graph, RouterDecision, WorkerTask
from schemas.micro_quant_schemas import EquityNarrativeOutput


class MockGraph:
    def __init__(self, return_val):
        self.return_val = return_val

    def invoke(self, state, *args, **kwargs):
        return self.return_val


class CapturingMockGraph:
    """MockGraph ที่จำ input ที่ได้รับไว้ — ใช้ตรวจสอบว่า instruction ที่ส่งให้ Archivist มีอะไรบ้าง"""

    def __init__(self, return_val):
        self.return_val = return_val
        self.received_inputs = []

    def invoke(self, state, *args, **kwargs):
        self.received_inputs.append(state)
        return self.return_val


@patch("agents.manager_agent._get_archivist_graph")
@patch("agents.manager_agent._get_equity_narrative_graph")
@patch("agents.manager_agent._get_equity_quant_graph")
@patch("agents.manager_agent._get_router_model")
@patch("agents.manager_agent.get_llm")
def test_equity_intel_flow_mocked_router(mock_llm, mock_router, mock_eq_quant, mock_eq_narrative, mock_archivist, equity_tmp_vault):
    class MockRouterModel:
        def invoke(self, *args, **kwargs):
            return RouterDecision(
                tasks=[WorkerTask(target="equity_intel", instruction="วิเคราะห์ AAPL")]
            )

        def with_structured_output(self, *args, **kwargs):
            return self

        def with_fallbacks(self, *args, **kwargs):
            return self

    mock_router.return_value = MockRouterModel()

    quant_valid = (
        '{"ticker": "AAPL", "market": "US", "value_score": 70.0, "quality_score": 80.0, '
        '"momentum_score": 60.0, "beta": 1.2, "volatility_pct": 25.0, "mdd_pct": -15.0, '
        '"upside_pct": 10.0, "downside_pct": -5.0, "evaluated_at": "2026-07-20T10:00:00+00:00", '
        '"data_quality_flags": []}'
    )
    mock_eq_quant.return_value = MockGraph({"messages": [AIMessage(content=quant_valid, name="equity_quant")]})

    narrative_valid = (
        '{"evaluated_at": "2026-07-20T10:00:00+00:00", "market_sentiment": "bullish", '
        '"key_themes": ["AI capex"], "tail_risks": [], "sources_summary": "test"}'
    )
    mock_eq_narrative.return_value = MockGraph({"messages": [AIMessage(content=narrative_valid, name="equity_narrative")]})

    mock_archivist.return_value = MockGraph({"messages": [AIMessage(content="saved", name="archivist")]})

    mock_narrative_output = EquityNarrativeOutput(
        narrative_analysis="ราคาหุ้นอยู่ในทิศทางขาขึ้น",
        base_case_summary="คงมุมมองเชิงบวก",
    )
    mock_structured_llm = MagicMock()
    mock_structured_llm.invoke.return_value = mock_narrative_output

    mock_llm_instance = MagicMock()
    mock_llm_instance.with_structured_output.return_value = mock_structured_llm
    mock_llm_instance.invoke.return_value = AIMessage(content="---\ntitle: x\nentity_type: research\n---\nReport")
    mock_llm.return_value = mock_llm_instance

    memory = MemorySaver()
    graph = build_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "test-equity-intel-1"}, "recursion_limit": 40}

    inputs = {"messages": [("user", "วิเคราะห์หุ้น AAPL แบบเชิงลึก")]}
    nodes_visited = []
    for event in graph.stream(inputs, config=config, stream_mode="updates"):
        for node_name, _state in event.items():
            nodes_visited.append(node_name)

    assert "supervisor" in nodes_visited
    assert "equity_quant" in nodes_visited
    assert "equity_narrative" in nodes_visited
    assert "equity_synthesizer" in nodes_visited
    assert "post_equity_intel" in nodes_visited
    assert "prepare_archivist" in nodes_visited
    assert "archivist" in nodes_visited

    final_state = graph.get_state(config).values
    assert final_state["equity_quant_score"]["ticker"] == "AAPL"
    assert final_state["equity_quant_score"]["value_score"] == 70.0
    assert final_state["equity_narrative_context"]["market_sentiment"] == "bullish"


@patch("agents.manager_agent._get_archivist_graph")
@patch("agents.manager_agent._get_equity_narrative_graph")
@patch("agents.manager_agent._get_equity_quant_graph")
@patch("agents.manager_agent._get_router_model")
@patch("agents.manager_agent.get_llm")
def test_equity_intel_flow_dictates_deterministic_archivist_filename(
    mock_llm, mock_router, mock_eq_quant, mock_eq_narrative, mock_archivist, tmp_vault
):
    """prepare_archivist_node ต้องบอก filename ให้ Archivist ตรงๆ จาก title: frontmatter — ไม่ปล่อยให้
    LLM เดาเอง (เจอจริงว่า re-run วันเดียวกันได้ filename ไม่ตรงกัน เช่น space vs underscore
    ทำให้เกิดไฟล์ซ้ำแทนที่จะ overwrite เดิม)"""
    class MockRouterModel:
        def invoke(self, *args, **kwargs):
            return RouterDecision(tasks=[WorkerTask(target="equity_intel", instruction="วิเคราะห์ AAPL")])

        def with_structured_output(self, *args, **kwargs):
            return self

        def with_fallbacks(self, *args, **kwargs):
            return self

    mock_router.return_value = MockRouterModel()

    quant_valid = (
        '{"ticker": "AAPL", "market": "US", "value_score": 70.0, "quality_score": 80.0, '
        '"momentum_score": 60.0, "beta": 1.2, "volatility_pct": 25.0, "mdd_pct": -15.0, '
        '"upside_pct": 10.0, "downside_pct": -5.0, "evaluated_at": "2026-07-20T10:00:00+00:00", '
        '"data_quality_flags": []}'
    )
    mock_eq_quant.return_value = MockGraph({"messages": [AIMessage(content=quant_valid, name="equity_quant")]})

    narrative_valid = (
        '{"evaluated_at": "2026-07-20T10:00:00+00:00", "market_sentiment": "bullish", '
        '"key_themes": [], "tail_risks": [], "sources_summary": "test"}'
    )
    mock_eq_narrative.return_value = MockGraph({"messages": [AIMessage(content=narrative_valid, name="equity_narrative")]})

    capturing_archivist = CapturingMockGraph({"messages": [AIMessage(content="saved", name="archivist")]})
    mock_archivist.return_value = capturing_archivist

    mock_narrative_output = EquityNarrativeOutput(
        narrative_analysis="ราคาหุ้นอยู่ในทิศทางขาขึ้น",
        base_case_summary="คงมุมมองเชิงบวก",
    )
    mock_structured_llm = MagicMock()
    mock_structured_llm.invoke.return_value = mock_narrative_output
    mock_llm_instance = MagicMock()
    mock_llm_instance.with_structured_output.return_value = mock_structured_llm
    mock_llm.return_value = mock_llm_instance

    memory = MemorySaver()
    graph = build_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "test-equity-intel-filename-1"}, "recursion_limit": 40}

    inputs = {"messages": [("user", "วิเคราะห์หุ้น AAPL แบบเชิงลึก")]}
    for _ in graph.stream(inputs, config=config, stream_mode="updates"):
        pass

    assert len(capturing_archivist.received_inputs) == 1
    archivist_instruction = capturing_archivist.received_inputs[0]["messages"][0].content

    assert "ต้องใช้ filename='AAPL Equity Analysis" in archivist_instruction
    assert "ห้ามดัดแปลง" in archivist_instruction


@patch("agents.manager_agent._get_archivist_graph")
@patch("agents.manager_agent._get_equity_narrative_graph")
@patch("agents.manager_agent._get_equity_quant_graph")
@patch("agents.manager_agent._get_router_model")
@patch("agents.manager_agent.get_llm")
def test_equity_intel_flow_quant_error_short_circuits_to_supervisor(
    mock_llm, mock_router, mock_eq_quant, mock_eq_narrative, mock_archivist, equity_tmp_vault
):
    """ถ้า equity_quant tool คืน Error string (JSON parse ไม่ผ่าน) ต้องไม่ไปต่อ equity_narrative"""
    class MockRouterModel:
        def invoke(self, *args, **kwargs):
            return RouterDecision(tasks=[WorkerTask(target="equity_intel", instruction="วิเคราะห์ BADTICKER")])

        def with_structured_output(self, *args, **kwargs):
            return self

        def with_fallbacks(self, *args, **kwargs):
            return self

    mock_router.return_value = MockRouterModel()
    mock_eq_quant.return_value = MockGraph(
        {"messages": [AIMessage(content="Error: ไม่สามารถคำนวณ Quant Signals ของ BADTICKER (US) ได้", name="equity_quant")]}
    )
    mock_eq_narrative.return_value = MockGraph({"messages": [AIMessage(content="{}", name="equity_narrative")]})
    mock_archivist.return_value = MockGraph({"messages": [AIMessage(content="saved", name="archivist")]})

    mock_llm_instance = MagicMock()
    mock_llm_instance.invoke.return_value = AIMessage(content="fallback")
    mock_llm.return_value = mock_llm_instance

    memory = MemorySaver()
    graph = build_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "test-equity-intel-error-1"}, "recursion_limit": 40}

    inputs = {"messages": [("user", "วิเคราะห์หุ้น BADTICKER")]}
    nodes_visited = []
    for event in graph.stream(inputs, config=config, stream_mode="updates"):
        for node_name, _state in event.items():
            nodes_visited.append(node_name)

    assert "equity_quant" in nodes_visited
    assert "equity_narrative" not in nodes_visited
    assert "equity_synthesizer" not in nodes_visited


@patch("agents.manager_agent._get_archivist_graph")
@patch("agents.manager_agent._get_equity_narrative_graph")
@patch("agents.manager_agent._get_equity_quant_graph")
@patch("agents.manager_agent._get_router_model")
@patch("agents.manager_agent.get_llm")
def test_equity_intel_flow_respects_save_to_vault_false(
    mock_llm, mock_router, mock_eq_quant, mock_eq_narrative, mock_archivist, tmp_vault
):
    """user บอก 'ดูเฉยๆ ไม่ต้องเซฟ' -> save_to_vault=False -> ต้องไม่ไป prepare_archivist/archivist"""
    class MockRouterModel:
        def invoke(self, *args, **kwargs):
            return RouterDecision(
                tasks=[WorkerTask(target="equity_intel", instruction="วิเคราะห์ AAPL ดูเฉยๆ", save_to_vault=False)]
            )

        def with_structured_output(self, *args, **kwargs):
            return self

        def with_fallbacks(self, *args, **kwargs):
            return self

    mock_router.return_value = MockRouterModel()

    quant_valid = (
        '{"ticker": "AAPL", "market": "US", "value_score": 70.0, "quality_score": 80.0, '
        '"momentum_score": 60.0, "beta": 1.2, "volatility_pct": 25.0, "mdd_pct": -15.0, '
        '"upside_pct": 10.0, "downside_pct": -5.0, "evaluated_at": "2026-07-20T10:00:00+00:00", '
        '"data_quality_flags": []}'
    )
    mock_eq_quant.return_value = MockGraph({"messages": [AIMessage(content=quant_valid, name="equity_quant")]})

    narrative_valid = (
        '{"evaluated_at": "2026-07-20T10:00:00+00:00", "market_sentiment": "bullish", '
        '"key_themes": [], "tail_risks": [], "sources_summary": "test"}'
    )
    mock_eq_narrative.return_value = MockGraph({"messages": [AIMessage(content=narrative_valid, name="equity_narrative")]})
    mock_archivist.return_value = MockGraph({"messages": [AIMessage(content="saved", name="archivist")]})

    mock_narrative_output = EquityNarrativeOutput(
        narrative_analysis="ราคาหุ้นอยู่ในทิศทางขาขึ้น",
        base_case_summary="คงมุมมองเชิงบวก",
    )
    mock_structured_llm = MagicMock()
    mock_structured_llm.invoke.return_value = mock_narrative_output
    mock_llm_instance = MagicMock()
    mock_llm_instance.with_structured_output.return_value = mock_structured_llm
    mock_llm.return_value = mock_llm_instance

    memory = MemorySaver()
    graph = build_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "test-equity-intel-no-save-1"}, "recursion_limit": 40}

    inputs = {"messages": [("user", "วิเคราะห์หุ้น AAPL ดูเฉยๆ ไม่ต้องเซฟ")]}
    nodes_visited = []
    for event in graph.stream(inputs, config=config, stream_mode="updates"):
        for node_name, _state in event.items():
            nodes_visited.append(node_name)

    assert "equity_synthesizer" in nodes_visited
    assert "post_equity_intel" in nodes_visited
    assert "prepare_archivist" not in nodes_visited
    assert "archivist" not in nodes_visited

    final_state = graph.get_state(config).values
    assert final_state["equity_save_to_vault"] is False
    # ผลวิเคราะห์เต็มต้องยังกลับไปหา user ได้ถึงแม้ไม่เซฟ (มิเรอร์ post_researcher_node no-save branch)
    assert "ราคาหุ้นอยู่ในทิศทางขาขึ้น" in final_state["messages"][-1].content

from ai.nick.blind_gate import NickBlindGate
from ai.nick.decision_contract import NickDecisionContract, NickKillCondition, NickPositionDecision
from ai.nick.trigger_workflow import NickTriggerWorkflow


def test_nick_blind_gate_blocks_real_holdings():
    gate = NickBlindGate()
    allowed, blocked = gate.validate_blocklist([
        "KB/thesis.md",
        "Team/PAINT_HOLDINGS.md",
        "notes/weekly.md",
    ])

    assert allowed == ["KB/thesis.md", "notes/weekly.md"]
    assert blocked == ["Team/PAINT_HOLDINGS.md"]


def test_nick_trigger_workflow_accepts_valid_modes():
    workflow = NickTriggerWorkflow()

    result = workflow.run("nick-weekly")

    assert result.trigger == "nick-weekly"
    assert result.status == "sent"
    assert "Nick workflow dispatched" in result.summary


def test_nick_decision_contract_requires_kill_conditions_and_cash_policy():
    decision = NickDecisionContract(
        trigger="nick-init",
        cash_weight=0.20,
        positions=[
            NickPositionDecision(
                symbol="AAPL",
                thesis="High-quality recurring cash flow business.",
                catalyst="Services growth and ecosystem monetization.",
                kill_conditions=[
                    NickKillCondition(
                        metric="gross_margin",
                        trigger="gross margin compresses materially for two quarters",
                    )
                ],
                target_weight=0.14,
                conviction=0.8,
            )
        ],
    )

    decision.validate()

    assert decision.to_dict()["positions"][0]["symbol"] == "AAPL"


def test_nick_decision_contract_rejects_cash_violation():
    decision = NickDecisionContract(
        trigger="nick-init",
        cash_weight=0.50,
        positions=[],
    )

    try:
        decision.validate()
        assert False, "Expected ValueError for cash ceiling violation"
    except ValueError:
        pass


def test_nick_dashboard_builds_summary_and_status():
    from ai.nick.dashboard import NickDashboard

    decision = NickDecisionContract(
        trigger="nick-weekly",
        cash_weight=0.20,
        positions=[
            NickPositionDecision(
                symbol="AAPL",
                thesis="High-quality recurring cash flow business.",
                catalyst="Services expansion.",
                kill_conditions=[
                    NickKillCondition(
                        metric="gross_margin",
                        trigger="gross margin compresses materially for two quarters",
                    )
                ],
                target_weight=0.14,
                conviction=0.8,
                status="intact",
            )
        ],
    )

    dashboard = NickDashboard(decision=decision)
    result = dashboard.render()

    assert result["trigger"] == "nick-weekly"
    assert result["portfolio_status"] == "active"
    assert result["positions"][0]["symbol"] == "AAPL"
    assert result["positions"][0]["status"] == "intact"


def test_nick_dashboard_comparison_vs_spy_flags_divergence():
    from ai.nick.dashboard import NickDashboard

    decision = NickDecisionContract(
        trigger="nick-weekly",
        cash_weight=0.20,
        positions=[
            NickPositionDecision(
                symbol="AAPL",
                thesis="High-quality recurring cash flow business.",
                catalyst="Services expansion.",
                kill_conditions=[
                    NickKillCondition(
                        metric="gross_margin",
                        trigger="gross margin compresses materially for two quarters",
                    )
                ],
                target_weight=0.14,
                conviction=0.8,
                status="evolving",
            )
        ],
    )

    dashboard = NickDashboard(decision=decision)
    comparison = dashboard.compare_to_spy(spy_return=0.06, nick_return=0.10)

    assert comparison["nick_return"] == 0.10
    assert comparison["spy_return"] == 0.06
    assert comparison["relative_signal"] == "outperforming"

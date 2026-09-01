from ai.nick.action_engine import NickActionEngine
from ai.nick.decision_contract import NickDecisionContract, NickKillCondition, NickPositionDecision


def test_nick_action_engine_sells_invalidated_position():
    decision = NickDecisionContract(
        trigger="nick-weekly",
        cash_weight=0.20,
        positions=[
            NickPositionDecision(
                symbol="META",
                thesis="Strong ad business with durable margins.",
                catalyst="Cloud monetization and AI efficiency gains.",
                kill_conditions=[
                    NickKillCondition(
                        metric="free_cash_flow",
                        trigger="free cash flow declines for two consecutive quarters",
                    )
                ],
                target_weight=0.12,
                conviction=0.65,
                status="invalidated",
            )
        ],
    )

    result = NickActionEngine().decide(decision)

    assert result.action == "sell"
    assert result.symbol == "META"


def test_nick_action_engine_trims_evolving_position():
    decision = NickDecisionContract(
        trigger="nick-weekly",
        cash_weight=0.20,
        positions=[
            NickPositionDecision(
                symbol="AAPL",
                thesis="Quality business with recurring services growth.",
                catalyst="Expanding ecosystem monetization.",
                kill_conditions=[
                    NickKillCondition(
                        metric="gross_margin",
                        trigger="gross margin compresses materially for two quarters",
                    )
                ],
                target_weight=0.08,
                conviction=0.72,
                status="evolving",
            )
        ],
    )

    result = NickActionEngine().decide(decision, current_weight=0.15, desired_weight=0.08)

    assert result.action == "trim"
    assert result.symbol == "AAPL"


def test_nick_action_engine_buy_if_position_is_intact_below_target():
    decision = NickDecisionContract(
        trigger="nick-init",
        cash_weight=0.20,
        positions=[
            NickPositionDecision(
                symbol="MSFT",
                thesis="Platform and AI flywheel with strong cash generation.",
                catalyst="Azure and productivity monetization.",
                kill_conditions=[
                    NickKillCondition(
                        metric="cloud_margin",
                        trigger="cloud margin expansion stalls for a full quarter",
                    )
                ],
                target_weight=0.18,
                conviction=0.85,
                status="intact",
            )
        ],
    )

    result = NickActionEngine().decide(decision, current_weight=0.07, desired_weight=0.18)

    assert result.action == "buy"
    assert result.symbol == "MSFT"


def test_nick_action_engine_defaults_to_no_trade_when_idle():
    decision = NickDecisionContract(
        trigger="nick-weekly",
        cash_weight=0.20,
        positions=[],
    )

    result = NickActionEngine().decide(decision)

    assert result.action == "no_trade"

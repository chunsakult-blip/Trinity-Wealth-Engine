from ai.nick.nick import Nick, NickLLMOutput


def make_output(
    *,
    decision="BUY",
    confidence=0.80,
    invalidation_conditions=None,
    valuation_view="undervalued",
):
    return NickLLMOutput(
        decision=decision,
        thesis="Test thesis",
        bull_case="Bull case",
        base_case="Base case",
        bear_case="Bear case",
        key_risks=["valuation"],
        valuation_view=valuation_view,
        position_sizing="5%",
        confidence=confidence,
        invalidation_conditions=(
            ["FCF deteriorates materially"]
            if invalidation_conditions is None
            else invalidation_conditions
        ),
        positions=[],
        notes="Guardrail test",
    )


def test_guardrail_low_confidence_forces_no_trade():
    nick = Nick()

    output = make_output(
        confidence=0.40,
    )

    result = nick._evaluate_risk_guardrail(
        output,
        {},
    )

    assert result["status"] == "triggered"
    assert result["decision"] == "NO_TRADE"
    assert result["original_decision"] == "BUY"
    assert result["checks"]["confidence_floor"] is False


def test_guardrail_buy_requires_invalidation_condition():
    nick = Nick()

    output = make_output(
        confidence=0.80,
        invalidation_conditions=[],
    )

    result = nick._evaluate_risk_guardrail(
        output,
        {},
    )

    assert result["status"] == "triggered"
    assert result["decision"] == "NO_TRADE"
    assert result["checks"]["buy_invalidation_required"] is False


def test_guardrail_overvalued_buy_is_downgraded_to_hold():
    nick = Nick()

    output = make_output(
        confidence=0.80,
        valuation_view="materially overvalued",
    )

    result = nick._evaluate_risk_guardrail(
        output,
        {},
    )

    assert result["status"] == "triggered"
    assert result["decision"] == "HOLD"
    assert result["original_decision"] == "BUY"
    assert result["checks"]["valuation_conflict"] is False


def test_guardrail_upstream_failure_forces_no_trade():
    nick = Nick()

    output = make_output(
        confidence=0.80,
    )

    package = {
        "financial": {
            "status": "failure",
        },
        "trinity": {
            "status": "success",
        },
    }

    result = nick._evaluate_risk_guardrail(
        output,
        package,
    )

    assert result["status"] == "triggered"
    assert result["decision"] == "NO_TRADE"
    assert result["checks"]["upstream_failures"] is False

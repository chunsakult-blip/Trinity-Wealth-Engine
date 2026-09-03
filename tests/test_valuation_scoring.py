from ai.research.investment.valuation import ValuationEngine


def test_price_to_fcf_is_not_double_counted():
    engine = ValuationEngine()

    result = engine.calculate(
        {
            "net_income": 100.0,
            "free_cash_flow": 100.0,
            "operating_income": 150.0,
            "depreciation_and_amortization": 50.0,
        },
        market_cap=2000.0,
        enterprise_value=2500.0,
    )

    # P/E = 20      -> 80
    # EV/EBITDA=12.5 -> 90
    # FCF yield=5%  -> 65
    #
    # Price/FCF = 20 is intentionally NOT scored separately.
    expected = round((80.0 + 90.0 + 65.0) / 3.0, 2)

    assert result.score == expected

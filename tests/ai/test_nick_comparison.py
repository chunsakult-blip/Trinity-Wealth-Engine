from ai.nick.comparison import NickComparisonEngine


def test_nick_comparison_vs_spy_detects_outperformance():
    engine = NickComparisonEngine()
    result = engine.compare_vs_spy(nick_return=0.12, spy_return=0.08)

    assert result.nick_return == 0.12
    assert result.spy_return == 0.08
    assert result.relative_signal == "outperforming"
    assert result.divergence == 0.04


def test_nick_comparison_vs_real_portfolio_detects_divergence():
    engine = NickComparisonEngine()
    result = engine.compare_vs_real_portfolio(
        nick_return=0.13,
        real_portfolio_return=0.09,
        spy_return=0.07,
    )

    assert result.real_portfolio_return == 0.09
    assert result.relative_signal == "alpha_vs_real_portfolio"
    assert result.divergence == 0.04

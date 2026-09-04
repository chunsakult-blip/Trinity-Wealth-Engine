from ai.nick.portfolio_intelligence import (
    PortfolioCandidate,
    PortfolioIntelligence,
)


def test_portfolio_allocator_respects_max_position_and_cash():
    engine = PortfolioIntelligence(
        max_position=20.0,
        min_cash=20.0,
        max_positions=10,
    )

    result = engine.allocate([
        PortfolioCandidate("AAPL", 95, 10, 1.0),
        PortfolioCandidate("MSFT", 90, 10, 1.0),
        PortfolioCandidate("NVDA", 88, 20, 1.0),
        PortfolioCandidate("GOOGL", 85, 20, 1.0),
        PortfolioCandidate("META", 80, 20, 1.0),
    ])

    assert result.cash_weight >= 20.0
    assert result.total_invested <= 80.0

    for position in result.positions:
        assert position.allocation <= 20.0


def test_portfolio_allocator_redistributes_capped_weight():
    engine = PortfolioIntelligence(
        max_position=20.0,
        min_cash=10.0,
        max_positions=5,
    )

    result = engine.allocate([
        PortfolioCandidate("AAPL", 100),
        PortfolioCandidate("MSFT", 90),
        PortfolioCandidate("NVDA", 80),
        PortfolioCandidate("GOOGL", 70),
        PortfolioCandidate("META", 60),
    ])

    allocations = {
        position.ticker: position.allocation
        for position in result.positions
    }

    assert allocations["AAPL"] == 20.0
    assert result.total_invested == 90.0
    assert result.cash_weight == 10.0


def test_high_risk_candidate_is_penalized():
    engine = PortfolioIntelligence(
        max_position=70.0,
        min_cash=20.0,
    )

    result = engine.allocate([
        PortfolioCandidate("RISKY", 95, risk_score=90),
        PortfolioCandidate("QUALITY", 85, risk_score=10),
    ])

    weights = {
        position.ticker: position.allocation
        for position in result.positions
    }

    assert weights["QUALITY"] > weights["RISKY"]


def test_empty_candidates_stay_in_cash():
    engine = PortfolioIntelligence()

    result = engine.allocate([])

    assert result.positions == []
    assert result.total_invested == 0.0
    assert result.cash_weight == 100.0

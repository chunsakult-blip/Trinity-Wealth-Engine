from dataclasses import dataclass


@dataclass(frozen=True)
class NickRuleConfig:

    # --------------------------------------------------------
    # Data
    # --------------------------------------------------------

    minimum_data_completeness: float = 0.60

    # --------------------------------------------------------
    # Balance Sheet
    # --------------------------------------------------------

    max_debt_to_equity: float = 2.50
    min_current_ratio: float = 0.80

    # --------------------------------------------------------
    # Valuation
    # --------------------------------------------------------

    max_pe_for_full_score: float = 40.0
    max_ev_ebitda_for_full_score: float = 35.0

    # --------------------------------------------------------
    # Score Weights
    # --------------------------------------------------------

    quality_weight: float = 0.25
    growth_weight: float = 0.25
    financial_health_weight: float = 0.20
    valuation_weight: float = 0.20
    momentum_weight: float = 0.10

    # --------------------------------------------------------
    # Tier thresholds
    # --------------------------------------------------------

    tier1_score: float = 75.0
    tier2_score: float = 55.0

    # --------------------------------------------------------
    # Quality thresholds
    # --------------------------------------------------------

    excellent_quality: float = 85.0
    strong_quality: float = 70.0


DEFAULT_NICK_RULES = NickRuleConfig()

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpportunityResult:

    composite_score: float
    opportunity_class: str


def clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:

    return max(
        low,
        min(
            high,
            float(value),
        ),
    )


def score_margin_of_safety(
    margin: float | None,
) -> float:

    if margin is None:
        return 50.0

    # 0% MOS = 50
    # 20% MOS = 70
    # 40% MOS = 90
    # 50%+ MOS = 100

    return clamp(
        50.0
        + margin * 100.0
    )


def classify_opportunity(
    quality_score: float,
    growth_score: float,
    health_score: float,
    valuation_score: float,
    moat_score: float,
    capital_allocation_score: float,
    margin_of_safety: float | None,
) -> OpportunityResult:

    mos_score = score_margin_of_safety(
        margin_of_safety
    )

    # Buffett-style architecture:
    #
    # Business quality > short-term momentum.
    #
    composite = (
        quality_score * 0.25
        + growth_score * 0.12
        + health_score * 0.15
        + valuation_score * 0.12
        + moat_score * 0.15
        + capital_allocation_score * 0.06
        + mos_score * 0.15
    )

    composite = clamp(
        composite
    )

    if (
        quality_score >= 85
        and moat_score >= 80
        and mos_score >= 85
    ):

        opportunity = (
            "EXCEPTIONAL_VALUE"
        )

    elif (
        quality_score >= 80
        and mos_score >= 75
    ):

        opportunity = (
            "GREAT_BUSINESS_AT_ATTRACTIVE_PRICE"
        )

    elif (
        quality_score >= 75
        and mos_score >= 60
    ):

        opportunity = (
            "QUALITY_WATCH"
        )

    elif (
        valuation_score >= 75
        and mos_score >= 70
    ):

        opportunity = (
            "VALUE_OPPORTUNITY"
        )

    else:

        opportunity = "WATCH"

    return OpportunityResult(
        composite_score=composite,
        opportunity_class=opportunity,
    )


if __name__ == "__main__":

    result = classify_opportunity(
        quality_score=95,
        growth_score=80,
        health_score=90,
        valuation_score=70,
        moat_score=90,
        capital_allocation_score=85,
        margin_of_safety=0.35,
    )

    print("")
    print("=" * 72)
    print("NICK V3 — OPPORTUNITY TEST")
    print("=" * 72)

    print(
        "Composite:",
        round(
            result.composite_score,
            2,
        ),
    )

    print(
        "Class:",
        result.opportunity_class,
    )

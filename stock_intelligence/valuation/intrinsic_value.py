from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntrinsicValueResult:

    dcf_low: float | None
    dcf_base: float | None
    dcf_high: float | None

    owner_earnings_value: float | None
    earnings_power_value: float | None

    intrinsic_value_low: float | None
    intrinsic_value_base: float | None
    intrinsic_value_high: float | None

    margin_of_safety: float | None


def _discounted_value(
    cash_flows: list[float],
    discount_rate: float,
    terminal_growth: float,
) -> float:

    if not cash_flows:
        return 0.0

    pv = 0.0

    for year, cash_flow in enumerate(
        cash_flows,
        start=1,
    ):

        pv += (
            cash_flow
            / (
                1.0 + discount_rate
            ) ** year
        )

    terminal = (
        cash_flows[-1]
        * (
            1.0 + terminal_growth
        )
        / (
            discount_rate
            - terminal_growth
        )
    )

    pv += (
        terminal
        / (
            1.0 + discount_rate
        ) ** len(cash_flows)
    )

    return pv


def dcf_per_share(
    fcf_per_share: float,
    growth_rate: float,
    discount_rate: float,
    terminal_growth: float,
    years: int = 10,
) -> float:

    if (
        fcf_per_share is None
        or fcf_per_share <= 0
    ):
        return 0.0

    if discount_rate <= terminal_growth:
        return 0.0

    cash_flows = []

    current = float(
        fcf_per_share
    )

    for _ in range(years):

        current *= (
            1.0 + growth_rate
        )

        cash_flows.append(
            current
        )

    return _discounted_value(
        cash_flows,
        discount_rate,
        terminal_growth,
    )


def calculate_intrinsic_value(
    price: float | None,
    fcf_per_share: float | None,
    normalized_owner_earnings_per_share: float | None,
    normalized_eps: float | None,
) -> IntrinsicValueResult:

    if (
        fcf_per_share is None
        or fcf_per_share <= 0
    ):

        return IntrinsicValueResult(
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    # Conservative / base / optimistic assumptions.
    dcf_low = dcf_per_share(
        fcf_per_share,
        growth_rate=0.06,
        discount_rate=0.11,
        terminal_growth=0.025,
    )

    dcf_base = dcf_per_share(
        fcf_per_share,
        growth_rate=0.10,
        discount_rate=0.10,
        terminal_growth=0.03,
    )

    dcf_high = dcf_per_share(
        fcf_per_share,
        growth_rate=0.14,
        discount_rate=0.095,
        terminal_growth=0.035,
    )

    owner_value = None

    if (
        normalized_owner_earnings_per_share
        is not None
        and normalized_owner_earnings_per_share > 0
    ):

        owner_value = (
            normalized_owner_earnings_per_share
            * 15.0
        )

    earnings_power_value = None

    if (
        normalized_eps is not None
        and normalized_eps > 0
    ):

        earnings_power_value = (
            normalized_eps
            * 18.0
        )

    values = [
        value
        for value in [
            dcf_low,
            owner_value,
            earnings_power_value,
        ]
        if value is not None
        and value > 0
    ]

    base_values = [
        value
        for value in [
            dcf_base,
            owner_value,
            earnings_power_value,
        ]
        if value is not None
        and value > 0
    ]

    high_values = [
        value
        for value in [
            dcf_high,
            owner_value,
            earnings_power_value,
        ]
        if value is not None
        and value > 0
    ]

    intrinsic_low = (
        sum(values) / len(values)
        if values
        else None
    )

    intrinsic_base = (
        sum(base_values) / len(base_values)
        if base_values
        else None
    )

    intrinsic_high = (
        sum(high_values) / len(high_values)
        if high_values
        else None
    )

    margin_of_safety = None

    if (
        price is not None
        and price > 0
        and intrinsic_base is not None
    ):

        margin_of_safety = (
            intrinsic_base
            / price
            - 1.0
        )

    return IntrinsicValueResult(
        dcf_low=dcf_low,
        dcf_base=dcf_base,
        dcf_high=dcf_high,
        owner_earnings_value=owner_value,
        earnings_power_value=earnings_power_value,
        intrinsic_value_low=intrinsic_low,
        intrinsic_value_base=intrinsic_base,
        intrinsic_value_high=intrinsic_high,
        margin_of_safety=margin_of_safety,
    )


if __name__ == "__main__":

    result = calculate_intrinsic_value(
        price=100.0,
        fcf_per_share=5.0,
        normalized_owner_earnings_per_share=5.0,
        normalized_eps=6.0,
    )

    print("")
    print("=" * 72)
    print("NICK V3 — INTRINSIC VALUE TEST")
    print("=" * 72)

    print(
        "DCF Low:",
        result.dcf_low,
    )

    print(
        "DCF Base:",
        result.dcf_base,
    )

    print(
        "DCF High:",
        result.dcf_high,
    )

    print(
        "Intrinsic Base:",
        result.intrinsic_value_base,
    )

    print(
        "Margin of Safety:",
        result.margin_of_safety,
    )

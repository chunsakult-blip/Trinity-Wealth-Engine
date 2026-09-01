from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PortfolioComparison:
    nick_return: float
    spy_return: float
    real_portfolio_return: float | None = None
    divergence: float | None = None
    relative_signal: str = "neutral"

    def to_dict(self) -> dict[str, Any]:
        return {
            "nick_return": self.nick_return,
            "spy_return": self.spy_return,
            "real_portfolio_return": self.real_portfolio_return,
            "divergence": self.divergence,
            "relative_signal": self.relative_signal,
        }


class NickComparisonEngine:
    """Compares Nick's independent recommendation against benchmark or real portfolio data."""

    @staticmethod
    def _clean_delta(value: float) -> float:
        return round(float(value), 6)

    def compare_vs_spy(self, *, nick_return: float, spy_return: float) -> PortfolioComparison:
        if nick_return > spy_return:
            signal = "outperforming"
        elif nick_return < spy_return:
            signal = "underperforming"
        else:
            signal = "neutral"

        return PortfolioComparison(
            nick_return=self._clean_delta(nick_return),
            spy_return=self._clean_delta(spy_return),
            divergence=self._clean_delta(nick_return - spy_return),
            relative_signal=signal,
        )

    def compare_vs_real_portfolio(
        self,
        *,
        nick_return: float,
        real_portfolio_return: float,
        spy_return: float,
    ) -> PortfolioComparison:
        divergence = self._clean_delta(nick_return - real_portfolio_return)
        if nick_return > real_portfolio_return:
            signal = "alpha_vs_real_portfolio"
        elif nick_return < real_portfolio_return:
            signal = "lagging_real_portfolio"
        else:
            signal = "neutral"

        return PortfolioComparison(
            nick_return=self._clean_delta(nick_return),
            spy_return=self._clean_delta(spy_return),
            real_portfolio_return=self._clean_delta(real_portfolio_return),
            divergence=divergence,
            relative_signal=signal,
        )

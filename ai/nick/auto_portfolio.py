from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NickTradePlan:
    symbol: str
    shares: float
    price_usd: float
    cost_thb: float
    action: str = "BUY"
    thesis: str = ""
    valuation_bias: str = "value_focused"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "shares": self.shares,
            "price_usd": self.price_usd,
            "cost_thb": self.cost_thb,
            "action": self.action,
            "thesis": self.thesis,
            "valuation_bias": self.valuation_bias,
        }


class NickAutoPortfolioSimulator:
    """Builds a Nick-style portfolio simulation from a selected list of quality/value names.

    The logic intentionally favors cheap-but-quality names, uses a reasonable cash budget,
    and can simulate daily decisions such as buying at the start of the run and selling when
    the profit target / valuation thesis breaks are hit.
    """

    def build_trade_plan(
        self,
        *,
        cash_thb: float,
        selected_symbols: list[str],
        price_map: dict[str, float],
        fx_rate: float = 36.5,
    ) -> list[dict[str, Any]]:
        if not selected_symbols:
            return []

        budget = float(cash_thb)
        allocated: list[dict[str, Any]] = []
        selected = [s for s in selected_symbols if s in price_map and float(price_map.get(s, 0.0)) > 0]
        if not selected:
            return []

        per_symbol_budget = budget / len(selected)
        for symbol in selected:
            price = float(price_map.get(symbol, 0.0))
            shares = per_symbol_budget / (price * fx_rate)
            if shares <= 0:
                continue
            cost_thb = shares * price * fx_rate
            allocated.append(
                {
                    "symbol": symbol,
                    "shares": round(shares, 4),
                    "price_usd": round(price, 4),
                    "cost_thb": round(cost_thb, 2),
                    "action": "BUY",
                    "valuation_bias": "value_focused",
                    "thesis": f"Nick buys {symbol} as a quality/value compounder with long-duration upside.",
                }
            )

        total_cost = sum(item["cost_thb"] for item in allocated)
        if total_cost > budget + 1e-9:
            scaling = budget / total_cost
            for item in allocated:
                scaled_cost = item["cost_thb"] * scaling
                item["shares"] = round((scaled_cost / (item["price_usd"] * fx_rate)), 4)
                item["cost_thb"] = round(scaled_cost, 2)

        return allocated

    def simulate_daily_run(
        self,
        *,
        symbols: list[str],
        starting_cash_thb: float,
        prices_by_day: dict[str, dict[str, float]],
        target_profit_pct: float = 0.18,
        fx_rate: float = 36.5,
    ) -> list[dict[str, Any]]:
        buy_plan = self.build_trade_plan(
            cash_thb=starting_cash_thb,
            selected_symbols=symbols,
            price_map=prices_by_day[next(iter(prices_by_day))],
            fx_rate=fx_rate,
        )
        if not buy_plan:
            return [{"date": next(iter(prices_by_day)), "action": "NO_TRADE", "cash_thb": starting_cash_thb}]

        ledger: list[dict[str, Any]] = [
            {
                "date": next(iter(prices_by_day)),
                "action": "BUY",
                "trade_count": len(buy_plan),
                "buy_total_thb": round(sum(item["cost_thb"] for item in buy_plan), 2),
                "cash_left_thb": round(starting_cash_thb - sum(item["cost_thb"] for item in buy_plan), 2),
                "positions": buy_plan,
            }
        ]

        ordered_days = sorted(prices_by_day)
        for day in ordered_days[1:]:
            prices = prices_by_day[day]
            actions: list[dict[str, Any]] = []
            for item in buy_plan:
                symbol = item["symbol"]
                current_price = float(prices.get(symbol, 0.0))
                if current_price <= 0:
                    continue
                entry = float(item["price_usd"])
                gain_pct = (current_price - entry) / entry
                if gain_pct >= target_profit_pct:
                    actions.append(
                        {
                            "date": day,
                            "action": "SELL",
                            "symbol": symbol,
                            "price_usd": round(current_price, 4),
                            "gain_pct": round(gain_pct, 4),
                            "reason": "profit target reached and thesis is realized",
                        }
                    )
                elif gain_pct <= -0.25:
                    actions.append(
                        {
                            "date": day,
                            "action": "SELL",
                            "symbol": symbol,
                            "price_usd": round(current_price, 4),
                            "gain_pct": round(gain_pct, 4),
                            "reason": "kill condition / value thesis broken",
                        }
                    )
            if actions:
                ledger.extend(actions)

        return ledger


__all__ = ["NickAutoPortfolioSimulator", "NickTradePlan"]

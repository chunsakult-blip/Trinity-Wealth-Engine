from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai.nick.auto_portfolio import NickAutoPortfolioSimulator


@dataclass
class NickPortfolioMonitor:
    """Produces the daily chart, trade log, and live-refresh snapshot for Nick's portfolio."""

    simulator: NickAutoPortfolioSimulator = None

    def __post_init__(self) -> None:
        if self.simulator is None:
            self.simulator = NickAutoPortfolioSimulator()

    def simulate_daily_history(
        self,
        *,
        selected_symbols: list[str],
        starting_cash_thb: float,
        prices_by_day: dict[str, dict[str, float]],
        profit_target_pct: float = 0.18,
        stop_loss_pct: float = -0.25,
        fx_rate: float = 36.5,
    ) -> dict[str, Any]:
        ordered_days = sorted(prices_by_day)
        if not ordered_days:
            return {"daily_series": [], "trade_log": []}

        first_day = ordered_days[0]
        buy_plan = self.simulator.build_trade_plan(
            cash_thb=starting_cash_thb,
            selected_symbols=selected_symbols,
            price_map=prices_by_day[first_day],
            fx_rate=fx_rate,
        )
        cash_remaining = starting_cash_thb - sum(item["cost_thb"] for item in buy_plan)
        positions = {item["symbol"]: {"shares": item["shares"], "entry_price": item["price_usd"]} for item in buy_plan}
        trade_log: list[dict[str, Any]] = [
            {
                "date": first_day,
                "action": "BUY",
                "symbol": "PORTFOLIO",
                "detail": buy_plan,
                "cash_after_thb": round(cash_remaining, 2),
            }
        ]

        daily_series: list[dict[str, Any]] = []
        for day in ordered_days:
            price_map = prices_by_day[day]
            portfolio_value = cash_remaining
            for symbol, position in positions.items():
                price = float(price_map.get(symbol, 0.0))
                if price <= 0:
                    continue
                portfolio_value += position["shares"] * price * fx_rate

            daily_series.append(
                {
                    "date": day,
                    "portfolio_value_thb": round(portfolio_value, 2),
                    "cash_thb": round(cash_remaining, 2),
                    "positions": positions,
                }
            )

            sell_actions = []
            for symbol, position in list(positions.items()):
                current_price = float(price_map.get(symbol, 0.0))
                if current_price <= 0:
                    continue
                gain_pct = (current_price - position["entry_price"]) / position["entry_price"]
                if gain_pct >= profit_target_pct or gain_pct <= stop_loss_pct:
                    trade_log.append(
                        {
                            "date": day,
                            "action": "SELL",
                            "symbol": symbol,
                            "price_usd": round(current_price, 4),
                            "gain_pct": round(gain_pct, 4),
                            "reason": "profit target or thesis break",
                        }
                    )
                    del positions[symbol]
                    cash_remaining = portfolio_value - sum(
                        p["shares"] * float(price_map.get(sym, 0.0)) * fx_rate
                        for sym, p in positions.items()
                    )
                    sell_actions.append(symbol)

        return {
            "daily_series": daily_series,
            "trade_log": trade_log,
            "buy_plan": buy_plan,
            "starting_cash_thb": starting_cash_thb,
        }

    def build_live_snapshot(
        self,
        *,
        price_map: dict[str, float],
        selected_symbols: list[str],
        cash_thb: float = 1_000_000.0,
        fx_rate: float = 36.5,
    ) -> dict[str, Any]:
        buy_plan = self.simulator.build_trade_plan(
            cash_thb=cash_thb,
            selected_symbols=selected_symbols,
            price_map=price_map,
            fx_rate=fx_rate,
        )
        positions = []
        total_value = cash_thb
        for item in buy_plan:
            market_price = float(price_map.get(item["symbol"], item["price_usd"]))
            market_value_thb = item["shares"] * market_price * fx_rate
            total_value += market_value_thb
            positions.append(
                {
                    "symbol": item["symbol"],
                    "shares": item["shares"],
                    "price_usd": round(market_price, 2),
                    "market_value_thb": round(market_value_thb, 2),
                    "weight_pct": round((market_value_thb / max(total_value, 1e-9)) * 100.0, 2),
                }
            )

        spy_price = float(price_map.get("SPY", 0.0))
        spy_prev = float(price_map.get("SPY_PREV", spy_price))
        benchmark = {
            "symbol": "SPY",
            "price_usd": round(spy_price, 2),
            "daily_move_pct": round(((spy_price - spy_prev) / max(abs(spy_prev), 1e-9)) * 100.0, 2),
        }

        return {
            "portfolio_value_thb": round(total_value, 2),
            "cash_thb": round(cash_thb - sum(item["cost_thb"] for item in buy_plan), 2),
            "positions": positions,
            "benchmark": benchmark,
            "trade_log": [
                {"date": "live", "action": "BUY", "symbol": item["symbol"], "cost_thb": item["cost_thb"]}
                for item in buy_plan
            ],
        }


__all__ = ["NickPortfolioMonitor"]

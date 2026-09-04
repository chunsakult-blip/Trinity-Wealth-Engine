from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PortfolioMonitoring:
    status: str
    allocation_drift: float
    cash_drift: float
    risk_exposure: float
    quality_score: float
    alerts: list[str]
    checks: dict[str, bool]


class PortfolioMonitoringEngine:
    """
    Lightweight deterministic portfolio monitoring.

    O(n)
    No LLM
    No external I/O
    Current holdings never enter NICK.
    """

    def evaluate(
        self,
        target_portfolio: dict[str, Any],
        current_portfolio: dict[str, Any] | None = None,
        *,
        max_allocation_drift: float = 5.0,
        min_cash: float = 20.0,
        max_risk_exposure: float = 45.0,
    ) -> PortfolioMonitoring:
        quality = target_portfolio.get("quality") or {}
        risk_guard = target_portfolio.get("risk_guard") or {}

        quality_score = float(quality.get("score", 0.0) or 0.0)
        risk_exposure = float(
            risk_guard.get("risk_exposure", 0.0) or 0.0
        )

        target_cash = float(
            target_portfolio.get("cash_weight", 0.0) or 0.0
        )

        current_cash = target_cash

        if current_portfolio is not None:
            current_cash = float(
                current_portfolio.get("cash_weight", target_cash) or 0.0
            )

        cash_drift = round(abs(current_cash - target_cash), 2)

        target_positions = {
            str(position.get("ticker", "")).strip().upper():
            float(position.get("allocation", 0.0) or 0.0)
            for position in target_portfolio.get("positions") or []
            if str(position.get("ticker", "")).strip()
        }

        current_positions = {
            str(position.get("ticker", "")).strip().upper():
            float(position.get("allocation", 0.0) or 0.0)
            for position in (
                current_portfolio.get("positions") or []
                if current_portfolio is not None
                else []
            )
            if str(position.get("ticker", "")).strip()
        }

        if current_portfolio is None:
            allocation_drift = 0.0
        else:
            tickers = set(target_positions) | set(current_positions)
            allocation_drift = round(
                max(
                    (
                        abs(
                            target_positions.get(ticker, 0.0)
                            - current_positions.get(ticker, 0.0)
                        )
                        for ticker in tickers
                    ),
                    default=0.0,
                ),
                2,
            )

        allocation_ok = (
            allocation_drift <= max_allocation_drift
        )

        cash_ok = current_cash >= min_cash
        risk_ok = risk_exposure <= max_risk_exposure
        quality_ok = quality_score >= 65.0
        guard_ok = bool(risk_guard.get("approved", True))

        checks = {
            "allocation_drift": allocation_ok,
            "cash": cash_ok,
            "risk_exposure": risk_ok,
            "quality": quality_ok,
            "risk_guard": guard_ok,
        }

        alerts: list[str] = []

        if not allocation_ok:
            alerts.append("Allocation drift exceeds threshold.")

        if not cash_ok:
            alerts.append("Cash buffer is below minimum.")

        if not risk_ok:
            alerts.append("Risk exposure exceeds threshold.")

        if not quality_ok:
            alerts.append("Portfolio quality is below monitoring threshold.")

        if not guard_ok:
            alerts.append("Portfolio risk guard is blocked.")

        status = "healthy" if all(checks.values()) else "attention"

        return PortfolioMonitoring(
            status=status,
            allocation_drift=allocation_drift,
            cash_drift=cash_drift,
            risk_exposure=round(risk_exposure, 2),
            quality_score=round(quality_score, 2),
            alerts=alerts,
            checks=checks,
        )

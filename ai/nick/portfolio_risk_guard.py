from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PortfolioRiskCheck:
    status: str
    approved: bool
    positions: list[dict[str, Any]]
    cash_weight: float
    total_invested: float
    risk_exposure: float
    reasons: list[str]
    checks: dict[str, bool]


class PortfolioRiskGuard:
    """Deterministic portfolio-level safety boundary."""

    def __init__(
        self,
        *,
        max_position: float = 20.0,
        min_cash: float = 20.0,
        max_risk_exposure: float = 45.0,
    ) -> None:
        if not 0.0 < max_position <= 100.0:
            raise ValueError("max_position must be within 0-100.")

        if not 0.0 <= min_cash < 100.0:
            raise ValueError("min_cash must be within 0-100.")

        if not 0.0 <= max_risk_exposure <= 100.0:
            raise ValueError(
                "max_risk_exposure must be within 0-100."
            )

        if max_position + min_cash > 100.0:
            raise ValueError(
                "max_position + min_cash cannot exceed 100."
            )

        self.max_position = float(max_position)
        self.min_cash = float(min_cash)
        self.max_risk_exposure = float(max_risk_exposure)

    def validate(
        self,
        portfolio: dict[str, Any],
    ) -> PortfolioRiskCheck:
        positions = portfolio.get("positions", [])

        if not isinstance(positions, list):
            positions = []

        reasons: list[str] = []
        checks: dict[str, bool] = {}

        normalized: list[dict[str, Any]] = []
        tickers: set[str] = set()

        total_invested = 0.0
        risk_exposure = 0.0
        duplicate_ticker = False
        invalid_position = False
        position_cap_ok = True

        for raw in positions:
            if not isinstance(raw, dict):
                invalid_position = True
                continue

            ticker = str(
                raw.get("ticker")
                or raw.get("symbol")
                or ""
            ).strip().upper()

            if not ticker:
                invalid_position = True
                continue

            try:
                allocation = float(
                    raw.get("allocation", 0.0) or 0.0
                )
            except (TypeError, ValueError):
                invalid_position = True
                continue

            try:
                risk_score = float(
                    raw.get("risk_score", 0.0) or 0.0
                )
            except (TypeError, ValueError):
                risk_score = 0.0

            if not 0.0 <= allocation <= 100.0:
                invalid_position = True
                continue

            if ticker in tickers:
                duplicate_ticker = True

            tickers.add(ticker)
            total_invested += allocation

            risk_score = min(max(risk_score, 0.0), 100.0)
            risk_exposure += allocation * (risk_score / 100.0)

            if allocation > self.max_position + 1e-9:
                position_cap_ok = False

            item = dict(raw)
            item["ticker"] = ticker
            item["allocation"] = round(allocation, 2)
            item["risk_score"] = round(risk_score, 2)
            normalized.append(item)

        total_invested = round(total_invested, 2)
        cash_weight = round(
            100.0 - total_invested,
            2,
        )
        risk_exposure = round(risk_exposure, 2)

        cash_ok = cash_weight >= self.min_cash - 1e-9
        invested_ok = total_invested <= 100.0 + 1e-9
        risk_ok = risk_exposure <= self.max_risk_exposure + 1e-9

        checks["position_cap"] = position_cap_ok
        checks["minimum_cash"] = cash_ok
        checks["total_invested"] = invested_ok
        checks["risk_exposure"] = risk_ok
        checks["duplicate_tickers"] = not duplicate_ticker
        checks["valid_positions"] = not invalid_position

        if not position_cap_ok:
            reasons.append("Position exceeds max_position limit.")

        if not cash_ok:
            reasons.append("Portfolio violates minimum cash floor.")

        if not invested_ok:
            reasons.append("Total invested allocation exceeds 100%.")

        if not risk_ok:
            reasons.append(
                "Portfolio risk exposure exceeds configured budget."
            )

        if duplicate_ticker:
            reasons.append("Duplicate ticker detected.")

        if invalid_position:
            reasons.append("Invalid portfolio position detected.")

        approved = all(checks.values())

        return PortfolioRiskCheck(
            status="passed" if approved else "blocked",
            approved=approved,
            positions=normalized,
            cash_weight=cash_weight,
            total_invested=total_invested,
            risk_exposure=risk_exposure,
            reasons=reasons,
            checks=checks,
        )


__all__ = ["PortfolioRiskCheck", "PortfolioRiskGuard"]

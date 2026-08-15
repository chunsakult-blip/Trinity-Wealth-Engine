"""Ledger Replay Engine for Portfolio Transaction Editing and Deletion.

Provides pure chronological trade replay, negative holding guards,
and transactional editing/deletion under portfolio locks according to DDD.
"""
import csv
import io
from pathlib import Path
from typing import Literal

from core.logger import get_logger
from tools._atomic_io import _atomic_write_to
from .constants import VAULT_PATH, PORTFOLIOS_DIR, _TRADES_LOG_HEADER
from .models import _now_iso, Holding, PortfolioState
from .core import (
    _load_or_init,
    _save,
    _recalc_all,
    _find_holding,
    _require_cash,
    _get_portfolio_lock,
    _normalize_portfolio_id,
    get_structured_portfolio_state,
)
from .trading import (
    _get_trades_log_filepath,
    _migrate_trades_log_if_needed,
    _sanitize_csv_field,
    CASH_THB_SYMBOL,
    CASH_USD_SYMBOL,
    _CASH_SYMBOLS,
    _FLOAT_EPS,
    _MONEY_DP,
    _COST_DP,
)
from .journal import _write_journal_entry

log = get_logger(__name__)


def _replay_symbol_trades(
    trades_rows: list[dict],
    symbol: str,
    currency: str,
) -> tuple[list[dict], float, float, float]:
    """Pure helper to replay all trades for a specific symbol chronologically.

    Args:
        trades_rows: List of dicts representing transactions for this symbol.
        symbol: Asset ticker symbol.
        currency: 'THB' or 'USD'.

    Returns:
        tuple of (updated_rows, final_units, final_avg_cost, total_realized_pnl_thb)

    Raises:
        ValueError: If cumulative units held drop below zero at any point.
    """
    sorted_rows = sorted(trades_rows, key=lambda r: str(r.get("Timestamp") or ""))
    units_held = 0.0
    cumulative_cost_native = 0.0
    avg_cost_native = 0.0
    total_realized_pnl_thb = 0.0
    updated_rows: list[dict] = []

    for row in sorted_rows:
        r = dict(row)
        action = str(r.get("Action") or "BUY").strip().upper()
        try:
            units = float(r.get("Units") or 0.0)
        except (ValueError, TypeError):
            units = 0.0
        try:
            price = float(r.get("Price") or 0.0)
        except (ValueError, TypeError):
            price = 0.0

        fx_raw = r.get("FX_Rate")
        fx_rate = float(fx_raw) if fx_raw is not None and str(fx_raw).strip() != "" else None

        if action == "BUY":
            amount_native = units * price
            cumulative_cost_native += amount_native
            units_held += units
            avg_cost_native = (cumulative_cost_native / units_held) if units_held > _FLOAT_EPS else 0.0
            cost_thb = amount_native * fx_rate if currency == "USD" and fx_rate is not None else amount_native

            r["Cost_THB"] = f"{cost_thb:.2f}"
            r["Realized_PnL_THB"] = ""
            r["Units"] = f"{units:g}"
            r["Price"] = f"{price:.2f}"
            updated_rows.append(r)

        elif action == "SELL":
            if units > units_held + _FLOAT_EPS:
                raise ValueError(
                    f"Replay failed for {symbol}: Insufficient units to sell at {r.get('Timestamp')} "
                    f"(held: {units_held:g}, tried to sell: {units:g})"
                )
            realized_native = (price - avg_cost_native) * units
            realized_thb = realized_native * fx_rate if currency == "USD" and fx_rate is not None else realized_native
            cost_thb = avg_cost_native * units * (fx_rate if currency == "USD" and fx_rate is not None else 1.0)

            units_held = max(0.0, units_held - units)
            cumulative_cost_native = units_held * avg_cost_native
            total_realized_pnl_thb += realized_thb

            r["Cost_THB"] = f"{cost_thb:.2f}"
            r["Realized_PnL_THB"] = f"{realized_thb:.2f}"
            r["Units"] = f"{units:g}"
            r["Price"] = f"{price:.2f}"
            updated_rows.append(r)
        else:
            updated_rows.append(r)

    final_units = max(0.0, units_held)
    final_avg = avg_cost_native if final_units > _FLOAT_EPS else 0.0
    return updated_rows, final_units, final_avg, total_realized_pnl_thb


def edit_transaction(
    tx_id: str,
    timestamp: str | None = None,
    units: float | None = None,
    price: float | None = None,
    fx_rate: float | None = None,
    notes: str | None = None,
    adjust_cash: bool = True,
    portfolio_id: str = "default",
) -> PortfolioState:
    """Edit an existing transaction.

    - If units, price, or timestamp are modified, triggers a full chronological replay for the symbol.
    - If only notes or fx_rate are modified, executes lightweight update.
    - Adjusts cash balance if adjust_cash=True based on native delta (units * price).
    - Self-acquires portfolio lock.
    """
    if units is not None and units <= 0:
        raise ValueError("units ต้องมากกว่า 0")
    if price is not None and price <= 0:
        raise ValueError("price ต้องมากกว่า 0")
    if fx_rate is not None and fx_rate <= 0:
        raise ValueError("fx_rate ต้องมากกว่า 0")

    lock = _get_portfolio_lock(portfolio_id)
    with lock:
        _migrate_trades_log_if_needed(portfolio_id)
        trades_log_path = _get_trades_log_filepath(portfolio_id)
        if not trades_log_path.exists() or trades_log_path.stat().st_size == 0:
            raise ValueError(f"Trades log not found for portfolio '{portfolio_id}'")

        all_rows: list[dict] = []
        target_idx: int = -1

        with trades_log_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                all_rows.append(row)
                if str(row.get("Transaction_ID") or "").strip() == tx_id:
                    target_idx = idx

        if target_idx == -1:
            raise ValueError(f"Transaction with ID '{tx_id}' not found")

        target_row = all_rows[target_idx]
        symbol = str(target_row.get("Symbol") or "").strip().upper()
        action = str(target_row.get("Action") or "BUY").strip().upper()
        currency = str(target_row.get("Currency") or "THB").strip().upper()

        old_units = float(target_row.get("Units") or 0.0)
        old_price = float(target_row.get("Price") or 0.0)
        old_fx_raw = target_row.get("FX_Rate")
        old_fx = float(old_fx_raw) if old_fx_raw is not None and str(old_fx_raw).strip() != "" else None
        old_timestamp = str(target_row.get("Timestamp") or "")

        new_units = units if units is not None else old_units
        new_price = price if price is not None else old_price
        new_fx = fx_rate if fx_rate is not None else old_fx
        new_timestamp = timestamp if timestamp is not None and timestamp.strip() else old_timestamp
        new_notes = _sanitize_csv_field(notes) if notes is not None else str(target_row.get("Notes") or "")

        requires_replay = (
            units is not None
            or price is not None
            or (timestamp is not None and timestamp.strip() != old_timestamp)
        )

        old_amount_native = old_units * old_price
        new_amount_native = new_units * new_price
        delta_native = new_amount_native - old_amount_native

        post, state = _load_or_init(portfolio_id=portfolio_id)

        # 1. Cash adjustment
        if adjust_cash and abs(delta_native) > _FLOAT_EPS:
            cash = _require_cash(state, currency)
            cash_sym = CASH_USD_SYMBOL if currency == "USD" else CASH_THB_SYMBOL
            if action == "BUY":
                new_cash_units = round(cash.units - delta_native, _MONEY_DP)
                if new_cash_units < -_FLOAT_EPS:
                    raise ValueError(
                        f"Insufficient cash in {cash_sym}: need {delta_native:,.2f} {currency}, available {cash.units:,.2f} {currency}"
                    )
                cash.units = new_cash_units
            elif action == "SELL":
                new_cash_units = round(cash.units + delta_native, _MONEY_DP)
                if new_cash_units < -_FLOAT_EPS:
                    raise ValueError(
                        f"Insufficient cash in {cash_sym} after sell adjustment: would result in negative cash ({new_cash_units:,.2f} {currency})"
                    )
                cash.units = new_cash_units

        # Update target row in memory
        target_row["Timestamp"] = new_timestamp
        target_row["Units"] = f"{new_units:g}"
        target_row["Price"] = f"{new_price:.2f}"
        target_row["FX_Rate"] = f"{new_fx:.4f}" if new_fx is not None else ""
        target_row["Notes"] = new_notes

        if not requires_replay:
            # Lightweight update path
            if currency == "USD" and new_fx is not None:
                cost_thb = new_amount_native * new_fx if action == "BUY" else (float(target_row.get("Cost_THB") or 0.0))
                target_row["Cost_THB"] = f"{cost_thb:.2f}"
            all_updated_rows = all_rows
        else:
            # Full Replay path
            symbol_rows = [r for r in all_rows if str(r.get("Symbol") or "").strip().upper() == symbol]
            other_rows = [r for r in all_rows if str(r.get("Symbol") or "").strip().upper() != symbol]

            updated_symbol_rows, final_units, final_avg_cost, _ = _replay_symbol_trades(
                symbol_rows, symbol, currency
            )

            all_updated_rows = updated_symbol_rows + other_rows
            all_updated_rows.sort(key=lambda r: str(r.get("Timestamp") or ""))

            # Update holding in portfolio state
            target_holding = _find_holding(state, symbol)
            if final_units < _FLOAT_EPS:
                if target_holding is not None:
                    state.holdings.remove(target_holding)
            else:
                if target_holding is None:
                    target_holding = Holding(
                        symbol=symbol,
                        asset_type="Stock",
                        units=round(final_units, _COST_DP),
                        currency=currency,
                    )
                    state.holdings.append(target_holding)
                else:
                    target_holding.units = round(final_units, _COST_DP)

                if currency == "USD":
                    target_holding.avg_cost_usd = round(final_avg_cost, _COST_DP)
                else:
                    target_holding.avg_cost_thb = round(final_avg_cost, _COST_DP)

                if getattr(target_holding, "dividend_source", None) == "synced":
                    target_holding.dividend_source = None

        # Re-derive total_realized_profit_ytd
        total_realized = 0.0
        for r in all_updated_rows:
            pnl_str = r.get("Realized_PnL_THB")
            if pnl_str and str(pnl_str).strip():
                try:
                    total_realized += float(pnl_str)
                except (ValueError, TypeError):
                    pass
        state.summary.total_realized_profit_ytd = round(total_realized, _MONEY_DP)

        # Save portfolio state and Trades_Log.csv
        _recalc_all(state)
        _save(post, state, portfolio_id=portfolio_id)

        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=_TRADES_LOG_HEADER, lineterminator="\n")
        writer.writeheader()
        for r in all_updated_rows:
            writer.writerow(r)
        _atomic_write_to(trades_log_path, out.getvalue())

        # Journal entry
        try:
            journal_msg = f"**[EDIT TRANSACTION - {symbol}]** {tx_id} ({action} {new_units:g} @ {new_price:,.2f} {currency})"
            _write_journal_entry(journal_msg, date_str=new_timestamp[:10], portfolio_id=portfolio_id)
        except Exception as ej:
            log.warning("Failed to append journal on edit transaction: %s", ej)

        return get_structured_portfolio_state(portfolio_id=portfolio_id)


def delete_transaction(
    tx_id: str,
    adjust_cash: bool = True,
    portfolio_id: str = "default",
) -> PortfolioState:
    """Delete an existing transaction by ID.

    - Performs full chronological replay on remaining trades for that symbol.
    - Adjusts cash if adjust_cash=True (refunds BUY cost, deducts SELL proceeds).
    - Self-acquires portfolio lock.
    """
    lock = _get_portfolio_lock(portfolio_id)
    with lock:
        _migrate_trades_log_if_needed(portfolio_id)
        trades_log_path = _get_trades_log_filepath(portfolio_id)
        if not trades_log_path.exists() or trades_log_path.stat().st_size == 0:
            raise ValueError(f"Trades log not found for portfolio '{portfolio_id}'")

        all_rows: list[dict] = []
        target_row: dict | None = None

        with trades_log_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if str(row.get("Transaction_ID") or "").strip() == tx_id:
                    target_row = row
                else:
                    all_rows.append(row)

        if target_row is None:
            raise ValueError(f"Transaction with ID '{tx_id}' not found")

        symbol = str(target_row.get("Symbol") or "").strip().upper()
        action = str(target_row.get("Action") or "BUY").strip().upper()
        currency = str(target_row.get("Currency") or "THB").strip().upper()
        old_units = float(target_row.get("Units") or 0.0)
        old_price = float(target_row.get("Price") or 0.0)
        old_amount_native = old_units * old_price

        post, state = _load_or_init(portfolio_id=portfolio_id)

        # 1. Cash adjustment
        if adjust_cash and old_amount_native > _FLOAT_EPS:
            cash = _require_cash(state, currency)
            cash_sym = CASH_USD_SYMBOL if currency == "USD" else CASH_THB_SYMBOL
            if action == "BUY":
                cash.units = round(cash.units + old_amount_native, _MONEY_DP)
            elif action == "SELL":
                new_cash_units = round(cash.units - old_amount_native, _MONEY_DP)
                if new_cash_units < -_FLOAT_EPS:
                    raise ValueError(
                        f"Cannot delete SELL transaction: insufficient cash in {cash_sym} to deduct proceeds "
                        f"({old_amount_native:,.2f} {currency}, balance: {cash.units:,.2f} {currency})"
                    )
                cash.units = new_cash_units

        # 2. Replay remaining trades for this symbol
        symbol_rows = [r for r in all_rows if str(r.get("Symbol") or "").strip().upper() == symbol]
        other_rows = [r for r in all_rows if str(r.get("Symbol") or "").strip().upper() != symbol]

        updated_symbol_rows, final_units, final_avg_cost, _ = _replay_symbol_trades(
            symbol_rows, symbol, currency
        )

        all_updated_rows = updated_symbol_rows + other_rows
        all_updated_rows.sort(key=lambda r: str(r.get("Timestamp") or ""))

        # 3. Update holding
        target_holding = _find_holding(state, symbol)
        if final_units < _FLOAT_EPS:
            if target_holding is not None:
                state.holdings.remove(target_holding)
        else:
            if target_holding is None:
                target_holding = Holding(
                    symbol=symbol,
                    asset_type="Stock",
                    units=round(final_units, _COST_DP),
                    currency=currency,
                )
                state.holdings.append(target_holding)
            else:
                target_holding.units = round(final_units, _COST_DP)

            if currency == "USD":
                target_holding.avg_cost_usd = round(final_avg_cost, _COST_DP)
            else:
                target_holding.avg_cost_thb = round(final_avg_cost, _COST_DP)

            if getattr(target_holding, "dividend_source", None) == "synced":
                target_holding.dividend_source = None

        # 4. Re-derive total_realized_profit_ytd
        total_realized = 0.0
        for r in all_updated_rows:
            pnl_str = r.get("Realized_PnL_THB")
            if pnl_str and str(pnl_str).strip():
                try:
                    total_realized += float(pnl_str)
                except (ValueError, TypeError):
                    pass
        state.summary.total_realized_profit_ytd = round(total_realized, _MONEY_DP)

        # 5. Save state & Trades_Log.csv
        _recalc_all(state)
        _save(post, state, portfolio_id=portfolio_id)

        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=_TRADES_LOG_HEADER, lineterminator="\n")
        writer.writeheader()
        for r in all_updated_rows:
            writer.writerow(r)
        _atomic_write_to(trades_log_path, out.getvalue())

        # 6. Journal
        try:
            journal_msg = f"**[DELETE TRANSACTION - {symbol}]** {tx_id} ({action} {old_units:g} @ {old_price:,.2f} {currency})"
            _write_journal_entry(journal_msg, portfolio_id=portfolio_id)
        except Exception as ej:
            log.warning("Failed to append journal on delete transaction: %s", ej)

        return get_structured_portfolio_state(portfolio_id=portfolio_id)

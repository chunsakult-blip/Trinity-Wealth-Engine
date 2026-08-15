import os
from pathlib import Path

VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", "./memories"))

# ทุกพอร์ต (รวมถึง 'default') เก็บที่ Portfolios/{id}/ เหมือนกันหมด ไม่มี special-case
# — ดู _get_portfolio_filepath / _get_holdings_dir / _get_watchlist_filepath /
# _get_watchlist_items_dir / _get_journal_filepath / _get_performance_filepath /
# _get_trades_log_filepath ในแต่ละโมดูลของ tools/portfolio/
PORTFOLIOS_DIR = VAULT_PATH / "20_Portfolio_Management/Current_Holdings/Portfolios"

GOALS_REL = os.getenv("GOALS_FILE", "20_Portfolio_Management/Goals/Goals.md")
GOALS_PATH = VAULT_PATH / GOALS_REL
GOALS_ITEMS_DIR = VAULT_PATH / "20_Portfolio_Management/Goals/Items"

_PERFORMANCE_LOG_HEADER = ["Date", "Total_NAV", "Total_Cost", "Unrealized_PnL", "Cash_Balance", "Realized_PnL_YTD", "Passive_Income_YTD"]
_TRADES_LOG_HEADER = ["Transaction_ID", "Timestamp", "Symbol", "Action", "Units", "Price", "Currency", "FX_Rate", "Cost_THB", "Realized_PnL_THB", "Notes"]

FUNDAMENTALS_TTL_SECONDS = 86400  # 24 hours
MARKET_CAP_MEGA_USD = 200_000_000_000
MARKET_CAP_LARGE_USD = 10_000_000_000
MARKET_CAP_MID_USD = 2_000_000_000


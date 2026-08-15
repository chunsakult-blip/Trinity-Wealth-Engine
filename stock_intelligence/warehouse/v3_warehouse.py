from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DATABASE = (
    "data/stock_intelligence_v3.sqlite"
)


class V3Warehouse:

    def __init__(
        self,
        path: str = DEFAULT_DATABASE,
    ):

        self.path = Path(path)

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize()

    def connect(self):

        conn = sqlite3.connect(
            self.path
        )

        conn.row_factory = sqlite3.Row

        return conn

    def initialize(self):

        with self.connect() as conn:

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS securities (
                    ticker TEXT PRIMARY KEY,
                    company_name TEXT,
                    exchange TEXT,
                    sector TEXT,
                    industry TEXT,
                    active INTEGER DEFAULT 1,
                    first_seen TEXT,
                    last_seen TEXT
                );

                CREATE TABLE IF NOT EXISTS fundamentals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    period_end TEXT,
                    fiscal_year INTEGER,

                    revenue REAL,
                    revenue_growth REAL,

                    eps REAL,
                    eps_growth REAL,

                    gross_profit REAL,
                    operating_income REAL,
                    net_income REAL,

                    free_cash_flow REAL,
                    operating_cash_flow REAL,
                    capital_expenditure REAL,

                    total_cash REAL,
                    total_debt REAL,
                    net_debt REAL,

                    total_assets REAL,
                    total_equity REAL,

                    shares_outstanding REAL,

                    roe REAL,
                    roa REAL,
                    roic REAL,

                    gross_margin REAL,
                    operating_margin REAL,
                    profit_margin REAL,

                    current_ratio REAL,
                    debt_to_equity REAL,

                    source TEXT,
                    fetched_at TEXT,

                    UNIQUE(ticker, period_end)
                );

                CREATE TABLE IF NOT EXISTS market_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,

                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,

                    market_cap REAL,

                    source TEXT,

                    UNIQUE(ticker, date)
                );

                CREATE TABLE IF NOT EXISTS valuation_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    as_of TEXT NOT NULL,

                    price REAL,
                    market_cap REAL,

                    pe REAL,
                    forward_pe REAL,
                    peg REAL,
                    price_to_sales REAL,
                    price_to_book REAL,
                    ev_to_ebitda REAL,

                    fcf_yield REAL,

                    dcf_low REAL,
                    dcf_base REAL,
                    dcf_high REAL,

                    owner_earnings_value REAL,
                    earnings_power_value REAL,

                    intrinsic_value_low REAL,
                    intrinsic_value_base REAL,
                    intrinsic_value_high REAL,

                    margin_of_safety REAL,

                    UNIQUE(ticker, as_of)
                );

                CREATE TABLE IF NOT EXISTS opportunity_scores (
                    ticker TEXT PRIMARY KEY,

                    quality_score REAL,
                    growth_score REAL,
                    health_score REAL,
                    valuation_score REAL,
                    moat_score REAL,
                    capital_allocation_score REAL,

                    intrinsic_value_score REAL,
                    margin_of_safety_score REAL,

                    composite_score REAL,

                    business_quality TEXT,
                    opportunity_class TEXT,

                    risk_flags TEXT,
                    hard_failures TEXT,

                    data_completeness REAL,
                    data_confidence REAL,

                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS universe_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT,
                    completed_at TEXT,
                    source TEXT,
                    total INTEGER,
                    succeeded INTEGER,
                    failed INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker
                    ON fundamentals(ticker);

                CREATE INDEX IF NOT EXISTS idx_market_history_ticker
                    ON market_history(ticker);

                CREATE INDEX IF NOT EXISTS idx_valuation_ticker
                    ON valuation_snapshots(ticker);

                CREATE INDEX IF NOT EXISTS idx_opportunity_score
                    ON opportunity_scores(composite_score);

                CREATE INDEX IF NOT EXISTS idx_opportunity_mos
                    ON opportunity_scores(margin_of_safety_score);
                """
            )

    def counts(self) -> dict[str, int]:

        tables = [
            "securities",
            "fundamentals",
            "market_history",
            "valuation_snapshots",
            "opportunity_scores",
            "universe_runs",
        ]

        result = {}

        with self.connect() as conn:

            for table in tables:

                row = conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table}"
                ).fetchone()

                result[table] = int(
                    row["n"]
                )

        return result


if __name__ == "__main__":

    db = V3Warehouse()

    print("")
    print("=" * 72)
    print("NICK V3 DATA WAREHOUSE")
    print("=" * 72)
    print("")

    for key, value in db.counts().items():
        print(
            f"{key:<25}: {value}"
        )

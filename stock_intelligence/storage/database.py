from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from stock_intelligence.models import StockRecord


class StockDatabase:

    def __init__(
        self,
        path: str = "data/stock_intelligence.sqlite",
    ):
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._initialize()

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self):
        with self.connect() as conn:

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stocks (
                    ticker TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    composite_score REAL NOT NULL,
                    data_completeness REAL NOT NULL,
                    fetched_at TEXT
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS universe (
                    ticker TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    discovered_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS screening_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    total INTEGER NOT NULL DEFAULT 0,
                    succeeded INTEGER NOT NULL DEFAULT 0,
                    failed INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_stocks_tier
                ON stocks(tier)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_stocks_score
                ON stocks(composite_score DESC)
                """
            )

    def save_universe(
        self,
        tickers: Iterable[str],
        source: str = "public_index_union",
    ):

        now = datetime.now(timezone.utc).isoformat()

        with self.connect() as conn:

            for ticker in tickers:

                ticker = str(ticker).upper().strip()

                if not ticker:
                    continue

                conn.execute(
                    """
                    INSERT INTO universe
                    (
                        ticker,
                        source,
                        active,
                        discovered_at
                    )
                    VALUES (?, ?, 1, ?)

                    ON CONFLICT(ticker)
                    DO UPDATE SET
                        source=excluded.source,
                        active=1
                    """,
                    (
                        ticker,
                        source,
                        now,
                    ),
                )

    def save_stock(
        self,
        record: StockRecord,
    ):

        payload = json.dumps(
            record.to_dict(),
            ensure_ascii=False,
            default=str,
        )

        with self.connect() as conn:

            conn.execute(
                """
                INSERT INTO stocks
                (
                    ticker,
                    payload,
                    tier,
                    decision,
                    composite_score,
                    data_completeness,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(ticker)
                DO UPDATE SET
                    payload=excluded.payload,
                    tier=excluded.tier,
                    decision=excluded.decision,
                    composite_score=excluded.composite_score,
                    data_completeness=excluded.data_completeness,
                    fetched_at=excluded.fetched_at
                """,
                (
                    record.ticker,
                    payload,
                    record.tier,
                    record.decision,
                    float(record.composite_score),
                    float(record.data_completeness),
                    record.fetched_at,
                ),
            )

    def count_universe(self) -> int:

        with self.connect() as conn:

            row = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM universe
                WHERE active=1
                """
            ).fetchone()

            return int(row["n"])

    def count_stocks(self) -> int:

        with self.connect() as conn:

            row = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM stocks
                """
            ).fetchone()

            return int(row["n"])

    def tier_counts(self) -> dict[str, int]:

        with self.connect() as conn:

            rows = conn.execute(
                """
                SELECT
                    tier,
                    COUNT(*) AS n
                FROM stocks
                GROUP BY tier
                ORDER BY tier
                """
            ).fetchall()

        return {
            row["tier"]: int(row["n"])
            for row in rows
        }

    def top_stocks(
        self,
        limit: int = 50,
    ):

        with self.connect() as conn:

            return conn.execute(
                """
                SELECT
                    ticker,
                    tier,
                    decision,
                    composite_score,
                    data_completeness
                FROM stocks
                ORDER BY composite_score DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

    def get_stock(
        self,
        ticker: str,
    ):

        with self.connect() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM stocks
                WHERE ticker=?
                """,
                (ticker.upper().strip(),),
            ).fetchone()

            return row

    def clear_stocks(self):

        with self.connect() as conn:
            conn.execute("DELETE FROM stocks")

    def clear_universe(self):

        with self.connect() as conn:
            conn.execute("DELETE FROM universe")

    def start_run(
        self,
        total: int,
    ) -> int:

        started = datetime.now(timezone.utc).isoformat()

        with self.connect() as conn:

            cursor = conn.execute(
                """
                INSERT INTO screening_runs
                (
                    started_at,
                    total
                )
                VALUES (?, ?)
                """,
                (
                    started,
                    int(total),
                ),
            )

            return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        succeeded: int,
        failed: int,
    ):

        completed = datetime.now(timezone.utc).isoformat()

        with self.connect() as conn:

            conn.execute(
                """
                UPDATE screening_runs
                SET
                    completed_at=?,
                    succeeded=?,
                    failed=?
                WHERE id=?
                """,
                (
                    completed,
                    int(succeeded),
                    int(failed),
                    int(run_id),
                ),
            )

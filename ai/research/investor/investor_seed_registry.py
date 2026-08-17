from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class InvestorSeedRegistry:
    """
    Stores investor-derived investment signals.

    Investor ownership is treated as a research signal,
    never as an automatic buy recommendation.
    """

    def __init__(
        self,
        db_path: str | Path = "data/intelligence/atlas_intelligence.db",
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS investor_seeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    investor_name TEXT NOT NULL,
                    ticker TEXT NOT NULL,

                    signal_type TEXT,
                    position_status TEXT,

                    source TEXT,
                    source_url TEXT,

                    observed_at TEXT,

                    confidence REAL DEFAULT 0.5,

                    metadata_json TEXT,

                    created_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_investor_seed_ticker
                    ON investor_seeds(ticker)
                """
            )

    def add(
        self,
        *,
        investor_name: str,
        ticker: str,
        signal_type: str = "holding",
        position_status: str = "active",
        source: str | None = None,
        source_url: str | None = None,
        observed_at: str | None = None,
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO investor_seeds (
                    investor_name,
                    ticker,
                    signal_type,
                    position_status,
                    source,
                    source_url,
                    observed_at,
                    confidence,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    investor_name,
                    ticker.upper(),
                    signal_type,
                    position_status,
                    source,
                    source_url,
                    observed_at,
                    max(0.0, min(1.0, confidence)),
                    json.dumps(
                        metadata or {},
                        ensure_ascii=False,
                        default=str,
                    ),
                    now,
                ),
            )

            return int(cursor.lastrowid)

    def signals_for(
        self,
        ticker: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM investor_seeds
                WHERE ticker = ?
                ORDER BY confidence DESC, created_at DESC
                """,
                (ticker.upper(),),
            ).fetchall()

        return [dict(row) for row in rows]

    def all(
        self,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM investor_seeds
                ORDER BY investor_name, ticker
                """
            ).fetchall()

        return [dict(row) for row in rows]

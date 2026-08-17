from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class KnowledgeStore:
    """
    Persistent evidence-first investment knowledge warehouse.

    Stores facts and research findings independently from
    any individual AI agent execution.
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
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    ticker TEXT NOT NULL,

                    knowledge_type TEXT NOT NULL,

                    topic TEXT NOT NULL,

                    statement TEXT NOT NULL,

                    value_json TEXT,

                    source TEXT,
                    source_url TEXT,

                    evidence_type TEXT,

                    confidence REAL DEFAULT 0.5,

                    observed_at TEXT,
                    retrieved_at TEXT NOT NULL,

                    agent_name TEXT,

                    metadata_json TEXT
                );

                CREATE INDEX IF NOT EXISTS
                    idx_knowledge_ticker
                    ON knowledge_items(ticker);

                CREATE INDEX IF NOT EXISTS
                    idx_knowledge_topic
                    ON knowledge_items(topic);

                CREATE INDEX IF NOT EXISTS
                    idx_knowledge_confidence
                    ON knowledge_items(confidence DESC);
                """
            )

    def add(
        self,
        *,
        ticker: str,
        knowledge_type: str,
        topic: str,
        statement: str,
        value: Any = None,
        source: str | None = None,
        source_url: str | None = None,
        evidence_type: str | None = None,
        confidence: float = 0.5,
        observed_at: str | None = None,
        agent_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        retrieved_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO knowledge_items (
                    ticker,
                    knowledge_type,
                    topic,
                    statement,
                    value_json,
                    source,
                    source_url,
                    evidence_type,
                    confidence,
                    observed_at,
                    retrieved_at,
                    agent_name,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker.upper(),
                    knowledge_type,
                    topic,
                    statement,
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        default=str,
                    ),
                    source,
                    source_url,
                    evidence_type,
                    max(0.0, min(1.0, confidence)),
                    observed_at,
                    retrieved_at,
                    agent_name,
                    json.dumps(
                        metadata or {},
                        ensure_ascii=False,
                        default=str,
                    ),
                ),
            )

            return int(cursor.lastrowid)

    def for_ticker(
        self,
        ticker: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM knowledge_items
                WHERE ticker = ?
                ORDER BY confidence DESC,
                         retrieved_at DESC
                """,
                (ticker.upper(),),
            ).fetchall()

        return [dict(row) for row in rows]

    def count(
        self,
        ticker: str | None = None,
    ) -> int:
        with self._connect() as conn:
            if ticker:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM knowledge_items
                    WHERE ticker = ?
                    """,
                    (ticker.upper(),),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM knowledge_items
                    """
                ).fetchone()

        return int(row["count"])

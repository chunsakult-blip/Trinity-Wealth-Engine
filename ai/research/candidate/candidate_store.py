from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CandidateStore:
    """
    Persistent investment candidate store.

    Responsibilities:
        - persist discovered candidates
        - preserve candidate identity
        - store ranking signals
        - maintain research status
        - provide ranked research queue

    This layer intentionally does NOT perform valuation.
    """

    def __init__(
        self,
        db_path: str | Path = (
            "data/intelligence/atlas_intelligence.db"
        ),
    ) -> None:
        self.db_path = Path(db_path)

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.db_path)
        )

        connection.row_factory = sqlite3.Row

        return connection

    def _initialize(self) -> None:
        with self._connect() as conn:

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    ticker TEXT NOT NULL,
                    company_name TEXT,

                    exchange TEXT,
                    country TEXT,

                    cik INTEGER,
                    security_type TEXT,

                    candidate_score REAL DEFAULT 0,
                    research_priority REAL DEFAULT 0,

                    investor_signal_score REAL DEFAULT 0,
                    universe_signal_score REAL DEFAULT 0,

                    research_status TEXT
                        DEFAULT 'discovered',

                    source TEXT,
                    source_url TEXT,

                    first_seen TEXT NOT NULL,
                    last_updated TEXT NOT NULL,

                    metadata_json TEXT,

                    UNIQUE(ticker, exchange)
                );

                CREATE INDEX IF NOT EXISTS
                    idx_candidates_score
                    ON candidates(candidate_score DESC);

                CREATE INDEX IF NOT EXISTS
                    idx_candidates_priority
                    ON candidates(research_priority DESC);

                CREATE INDEX IF NOT EXISTS
                    idx_candidates_status
                    ON candidates(research_status);

                CREATE INDEX IF NOT EXISTS
                    idx_candidates_ticker
                    ON candidates(ticker);
                """
            )

    def upsert(
        self,
        record: dict[str, Any],
    ) -> None:

        ticker = str(
            record.get("ticker", "")
        ).strip().upper()

        exchange = str(
            record.get("exchange", "")
        ).strip().upper()

        if not ticker:
            raise ValueError(
                "Candidate ticker is required."
            )

        if not exchange:
            raise ValueError(
                "Candidate exchange is required."
            )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        metadata = dict(record)

        with self._connect() as conn:

            conn.execute(
                """
                INSERT INTO candidates (
                    ticker,
                    company_name,
                    exchange,
                    country,
                    cik,
                    security_type,

                    candidate_score,
                    research_priority,

                    investor_signal_score,
                    universe_signal_score,

                    research_status,

                    source,
                    source_url,

                    first_seen,
                    last_updated,

                    metadata_json
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?,
                    ?, ?,
                    ?, ?,
                    ?
                )

                ON CONFLICT(ticker, exchange)

                DO UPDATE SET

                    company_name =
                        excluded.company_name,

                    country =
                        excluded.country,

                    cik =
                        excluded.cik,

                    security_type =
                        excluded.security_type,

                    candidate_score =
                        excluded.candidate_score,

                    research_priority =
                        excluded.research_priority,

                    investor_signal_score =
                        excluded.investor_signal_score,

                    universe_signal_score =
                        excluded.universe_signal_score,

                    research_status =
                        excluded.research_status,

                    source =
                        excluded.source,

                    source_url =
                        excluded.source_url,

                    last_updated =
                        excluded.last_updated,

                    metadata_json =
                        excluded.metadata_json
                """,
                (
                    ticker,
                    record.get(
                        "company_name"
                    ),
                    exchange,
                    record.get(
                        "country"
                    ),
                    record.get(
                        "cik"
                    ),
                    record.get(
                        "security_type"
                    ),

                    float(
                        record.get(
                            "candidate_score",
                            0,
                        ) or 0
                    ),

                    float(
                        record.get(
                            "research_priority",
                            0,
                        ) or 0
                    ),

                    float(
                        record.get(
                            "investor_signal_score",
                            0,
                        ) or 0
                    ),

                    float(
                        record.get(
                            "universe_signal_score",
                            0,
                        ) or 0
                    ),

                    record.get(
                        "research_status",
                        "discovered",
                    ),

                    record.get(
                        "source"
                    ),

                    record.get(
                        "source_url"
                    ),

                    now,
                    now,

                    json.dumps(
                        metadata,
                        ensure_ascii=False,
                        default=str,
                    ),
                ),
            )

    def bulk_upsert(
        self,
        records: list[dict[str, Any]],
    ) -> int:

        count = 0

        for record in records:
            self.upsert(record)
            count += 1

        return count

    def top(
        self,
        limit: int = 600,
    ) -> list[dict[str, Any]]:

        limit = max(
            1,
            int(limit),
        )

        with self._connect() as conn:

            rows = conn.execute(
                """
                SELECT *
                FROM candidates

                ORDER BY
                    candidate_score DESC,
                    research_priority DESC,
                    ticker ASC

                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        results: list[dict[str, Any]] = []

        for row in rows:

            item = dict(row)

            metadata_raw = item.get(
                "metadata_json"
            )

            if metadata_raw:

                try:
                    metadata = json.loads(
                        metadata_raw
                    )
                except (
                    TypeError,
                    ValueError,
                    json.JSONDecodeError,
                ):
                    metadata = {}

                if isinstance(metadata, dict):

                    for key, value in metadata.items():

                        if (
                            key not in item
                            or item.get(key) is None
                        ):
                            item[key] = value

            results.append(item)

        return results

    def count(self) -> int:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM candidates
                """
            ).fetchone()

        return int(
            row["count"]
        )

    def count_by_status(
        self,
    ) -> dict[str, int]:

        with self._connect() as conn:

            rows = conn.execute(
                """
                SELECT
                    research_status,
                    COUNT(*) AS count

                FROM candidates

                GROUP BY research_status
                """
            ).fetchall()

        return {
            str(row["research_status"]):
                int(row["count"])
            for row in rows
        }

    def summary(
        self,
    ) -> dict[str, Any]:

        return {
            "total_candidates":
                self.count(),

            "status_counts":
                self.count_by_status(),

            "database":
                str(self.db_path),
        }

    def set_status(
        self,
        ticker: str,
        status: str,
    ) -> None:

        now = datetime.now(
            timezone.utc
        ).isoformat()

        with self._connect() as conn:

            conn.execute(
                """
                UPDATE candidates

                SET
                    research_status = ?,
                    last_updated = ?

                WHERE ticker = ?
                """,
                (
                    status,
                    now,
                    ticker.upper(),
                ),
            )

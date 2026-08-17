from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path(
    "data/stock_intelligence_v3.sqlite"
)


def column_names(
    conn,
    table,
):
    rows = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return {
        row[1]
        for row in rows
    }


def add_column_if_missing(
    conn,
    table,
    column,
    definition,
):
    columns = column_names(
        conn,
        table,
    )

    if column not in columns:

        conn.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )

        print(
            f"ADDED: {table}.{column}"
        )

    else:

        print(
            f"EXISTS: {table}.{column}"
        )


def main():

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        DB_PATH
    )

    try:

        print("")
        print("=" * 80)
        print("NICK V3 — SCHEMA MIGRATION")
        print("=" * 80)
        print("")

        # --------------------------------------------------------------
        # SECURITIES
        # --------------------------------------------------------------

        add_column_if_missing(
            conn,
            "securities",
            "security_name",
            "TEXT",
        )

        add_column_if_missing(
            conn,
            "securities",
            "security_type",
            "TEXT",
        )

        add_column_if_missing(
            conn,
            "securities",
            "exchange",
            "TEXT",
        )

        add_column_if_missing(
            conn,
            "securities",
            "source",
            "TEXT",
        )

        add_column_if_missing(
            conn,
            "securities",
            "fetched_at",
            "TEXT",
        )

        # --------------------------------------------------------------
        # FUNDAMENTALS
        # --------------------------------------------------------------

        for column, definition in [

            ("period_end", "TEXT"),
            ("fiscal_year", "INTEGER"),

            ("revenue", "REAL"),
            ("revenue_growth", "REAL"),

            ("eps", "REAL"),
            ("eps_growth", "REAL"),

            ("gross_profit", "REAL"),
            ("operating_income", "REAL"),
            ("net_income", "REAL"),

            ("free_cash_flow", "REAL"),
            ("operating_cash_flow", "REAL"),
            ("capital_expenditure", "REAL"),

            ("total_cash", "REAL"),
            ("total_debt", "REAL"),
            ("net_debt", "REAL"),

            ("total_assets", "REAL"),
            ("total_equity", "REAL"),

            ("shares_outstanding", "REAL"),

            ("roe", "REAL"),
            ("roa", "REAL"),
            ("roic", "REAL"),

            ("gross_margin", "REAL"),
            ("operating_margin", "REAL"),
            ("profit_margin", "REAL"),

            ("current_ratio", "REAL"),
            ("debt_to_equity", "REAL"),

            ("source", "TEXT"),
            ("fetched_at", "TEXT"),

        ]:

            add_column_if_missing(
                conn,
                "fundamentals",
                column,
                definition,
            )

        # --------------------------------------------------------------
        # MARKET HISTORY
        # --------------------------------------------------------------

        for column, definition in [

            ("open", "REAL"),
            ("high", "REAL"),
            ("low", "REAL"),
            ("close", "REAL"),
            ("volume", "REAL"),
            ("market_cap", "REAL"),
            ("source", "TEXT"),

        ]:

            add_column_if_missing(
                conn,
                "market_history",
                column,
                definition,
            )

        # --------------------------------------------------------------
        # VALUATION
        # --------------------------------------------------------------

        for column, definition in [

            ("price", "REAL"),
            ("market_cap", "REAL"),

            ("pe", "REAL"),
            ("forward_pe", "REAL"),
            ("peg", "REAL"),
            ("price_to_sales", "REAL"),
            ("price_to_book", "REAL"),
            ("ev_to_ebitda", "REAL"),

            ("fcf_yield", "REAL"),

            ("dcf_low", "REAL"),
            ("dcf_base", "REAL"),
            ("dcf_high", "REAL"),

            ("owner_earnings_value", "REAL"),
            ("earnings_power_value", "REAL"),

            ("intrinsic_value_low", "REAL"),
            ("intrinsic_value_base", "REAL"),
            ("intrinsic_value_high", "REAL"),

            ("margin_of_safety", "REAL"),

        ]:

            add_column_if_missing(
                conn,
                "valuation_snapshots",
                column,
                definition,
            )

        # --------------------------------------------------------------
        # OPPORTUNITY
        # --------------------------------------------------------------

        for column, definition in [

            ("quality_score", "REAL"),
            ("growth_score", "REAL"),
            ("health_score", "REAL"),
            ("valuation_score", "REAL"),
            ("moat_score", "REAL"),
            ("capital_allocation_score", "REAL"),

            ("intrinsic_value_score", "REAL"),
            ("margin_of_safety_score", "REAL"),

            ("composite_score", "REAL"),

            ("business_quality", "TEXT"),
            ("opportunity_class", "TEXT"),

            ("risk_flags", "TEXT"),
            ("hard_failures", "TEXT"),

            ("data_completeness", "REAL"),
            ("data_confidence", "REAL"),

            ("updated_at", "TEXT"),

        ]:

            add_column_if_missing(
                conn,
                "opportunity_scores",
                column,
                definition,
            )

        conn.commit()

        print("")
        print("=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)

    finally:

        conn.close()


if __name__ == "__main__":
    main()

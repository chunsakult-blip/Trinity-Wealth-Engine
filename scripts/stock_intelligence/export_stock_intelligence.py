from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from stock_intelligence.storage.database import StockDatabase


def export_csv(
    output: str,
):

    db = StockDatabase()

    output_path = Path(output)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with db.connect() as conn:

        rows = conn.execute(
            """
            SELECT payload
            FROM stocks
            ORDER BY composite_score DESC
            """
        ).fetchall()

    if not rows:

        print("No stock records found.")
        return

    records = [
        json.loads(row["payload"])
        for row in rows
    ]

    fieldnames = sorted(
        {
            key
            for record in records
            for key in record.keys()
        }
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        for record in records:
            writer.writerow(record)

    print("")
    print("EXPORT COMPLETE")
    print("Records:", len(records))
    print("File:", output_path)


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        default="data/stock_intelligence.csv",
    )

    args = parser.parse_args()

    export_csv(
        args.output
    )


if __name__ == "__main__":
    main()

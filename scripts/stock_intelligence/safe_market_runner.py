from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ======================================================================
# PROJECT PATH
# ======================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ======================================================================
# IMPORTS
# ======================================================================

from stock_intelligence.ingestion.large_fundamental_ingestion import (
    ingest_stock,
)

from stock_intelligence.market.us_universe import (
    discover_us_equities,
)

from stock_intelligence.warehouse.v3_warehouse import (
    V3Warehouse,
)


# ======================================================================
# CONFIGURATION
# ======================================================================

DB_PATH = PROJECT_ROOT / "data" / "stock_intelligence_v3.sqlite"

STATE_PATH = (
    PROJECT_ROOT
    / "data"
    / "nick_v3_request_budget.json"
)

# Hard external limit
DAILY_LIMIT = 1000

# Never touch this reserve
SAFETY_RESERVE = 200

# Maximum budget we intentionally consume
USABLE_BUDGET = (
    DAILY_LIMIT
    - SAFETY_RESERVE
)

# ingest_stock() currently performs:
#
#   financials
#   balance_sheet
#   cashflow
#   market history
#
# = 4 operations per attempt
#
# With MAX_RETRIES = 3:
#
#   4 x 3 = 12 worst-case operations / stock
#
# We therefore budget against the WORST CASE.
OPERATIONS_PER_ATTEMPT = 4
MAX_RETRIES = 3
WORST_CASE_OPERATIONS_PER_STOCK = (
    OPERATIONS_PER_ATTEMPT
    * MAX_RETRIES
)

MAX_STOCKS_PER_RUN = (
    USABLE_BUDGET
    // WORST_CASE_OPERATIONS_PER_STOCK
)

# Slow enough to reduce pressure on upstream source.
REQUEST_DELAY = 1.5

CHECKPOINT_EVERY = 10


# ======================================================================
# TIME
# ======================================================================

def utc_now():
    return datetime.now(
        timezone.utc
    )


def today_key():
    # Keep UTC because the external daily quota
    # may reset on UTC boundaries.
    return utc_now().strftime(
        "%Y-%m-%d"
    )


# ======================================================================
# STATE
# ======================================================================

def default_state():
    return {
        "date": today_key(),

        "estimated_operations_used": 0,

        "stocks_processed": 0,

        "success": 0,

        "failed": 0,

        "started_at": utc_now().isoformat(),

        "updated_at": utc_now().isoformat(),
    }


def save_state(state):

    state["updated_at"] = (
        utc_now().isoformat()
    )

    STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = (
        STATE_PATH.with_suffix(
            ".tmp"
        )
    )

    temp_path.write_text(
        json.dumps(
            state,
            indent=2,
        ),
        encoding="utf-8",
    )

    temp_path.replace(
        STATE_PATH
    )


def load_state():

    STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not STATE_PATH.exists():

        state = default_state()

        save_state(state)

        return state

    try:

        state = json.loads(
            STATE_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        state = default_state()

        save_state(state)

        return state

    # Daily reset
    if state.get("date") != today_key():

        state = default_state()

        save_state(state)

    return state


# ======================================================================
# DATABASE
# ======================================================================

def existing_tickers(db):

    with db.connect() as conn:

        rows = conn.execute(
            """
            SELECT DISTINCT ticker
            FROM fundamentals
            """
        ).fetchall()

    return {
        row["ticker"]
        for row in rows
    }


# ======================================================================
# MAIN
# ======================================================================

def main():

    print("")
    print("=" * 90)
    print(
        "NICK V3 — SAFE LARGE-SCALE DATA WAREHOUSE V2"
    )
    print("=" * 90)
    print("")

    print(
        f"Daily hard limit             : "
        f"{DAILY_LIMIT:,}"
    )

    print(
        f"Safety reserve               : "
        f"{SAFETY_RESERVE:,}"
    )

    print(
        f"Usable budget                : "
        f"{USABLE_BUDGET:,}"
    )

    print(
        f"Operations / attempt        : "
        f"{OPERATIONS_PER_ATTEMPT}"
    )

    print(
        f"Maximum retries             : "
        f"{MAX_RETRIES}"
    )

    print(
        f"Worst-case operations/stock : "
        f"{WORST_CASE_OPERATIONS_PER_STOCK}"
    )

    print(
        f"Maximum stocks/run          : "
        f"{MAX_STOCKS_PER_RUN}"
    )

    print(
        f"Request delay               : "
        f"{REQUEST_DELAY}s"
    )

    print("")

    # --------------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------------

    db = V3Warehouse(
        str(DB_PATH)
    )

    # --------------------------------------------------------------
    # STATE
    # --------------------------------------------------------------

    state = load_state()

    used = int(
        state.get(
            "estimated_operations_used",
            0,
        )
    )

    remaining_budget = (
        USABLE_BUDGET
        - used
    )

    print(
        f"Budget already used today   : "
        f"{used:,}"
    )

    print(
        f"Budget remaining             : "
        f"{max(remaining_budget, 0):,}"
    )

    print("")

    if remaining_budget < WORST_CASE_OPERATIONS_PER_STOCK:

        print(
            "DAILY SAFE BUDGET EXHAUSTED."
        )

        print(
            "Runner will resume after the daily reset."
        )

        return

    # --------------------------------------------------------------
    # UNIVERSE
    # --------------------------------------------------------------

    print(
        "Discovering US equity universe..."
    )

    stocks = discover_us_equities()

    print(
        f"Universe discovered          : "
        f"{len(stocks):,}"
    )

    # --------------------------------------------------------------
    # EXISTING DATA
    # --------------------------------------------------------------

    completed = existing_tickers(
        db
    )

    print(
        f"Already processed            : "
        f"{len(completed):,}"
    )

    pending = [
        stock
        for stock in stocks
        if stock.ticker not in completed
    ]

    print(
        f"Remaining universe           : "
        f"{len(pending):,}"
    )

    print("")

    # --------------------------------------------------------------
    # RUN LIMIT
    # --------------------------------------------------------------

    budget_stock_limit = (
        remaining_budget
        // WORST_CASE_OPERATIONS_PER_STOCK
    )

    run_limit = min(
        MAX_STOCKS_PER_RUN,
        budget_stock_limit,
        len(pending),
    )

    if run_limit <= 0:

        print(
            "No safe stock capacity remaining."
        )

        return

    batch = pending[
        :run_limit
    ]

    estimated_budget = (
        len(batch)
        * WORST_CASE_OPERATIONS_PER_STOCK
    )

    print(
        f"This run                   : "
        f"{len(batch):,} stocks"
    )

    print(
        f"Worst-case budget          : "
        f"{estimated_budget:,}"
    )

    print("")

    print(
        "======================================================================"
    )

    print(
        "STARTING CONTROLLED INGESTION"
    )

    print(
        "======================================================================"
    )

    print("")

    success = 0
    failed = 0

    processed_this_run = 0

    # --------------------------------------------------------------
    # INGESTION LOOP
    # --------------------------------------------------------------

    for index, stock in enumerate(
        batch,
        start=1,
    ):

        ticker = stock.ticker

        # ----------------------------------------------------------
        # HARD LOCAL BUDGET CHECK
        # ----------------------------------------------------------

        if (
            used
            + WORST_CASE_OPERATIONS_PER_STOCK
            > USABLE_BUDGET
        ):

            print("")

            print(
                "SAFE REQUEST BUDGET REACHED."
            )

            print(
                f"Used       : {used:,}"
            )

            print(
                f"Limit      : {USABLE_BUDGET:,}"
            )

            break

        print(
            f"[{index:04d}/{len(batch):04d}] "
            f"{ticker:<8} "
            f"processing..."
        )

        # ----------------------------------------------------------
        # INGEST
        # ----------------------------------------------------------

        result = ingest_stock(
            db,
            stock,
        )

        # ----------------------------------------------------------
        # CONSERVATIVE ACCOUNTING
        #
        # We intentionally charge the WORST CASE,
        # even when the actual request count was lower.
        # This prevents accidental quota exhaustion.
        # ----------------------------------------------------------

        used += (
            WORST_CASE_OPERATIONS_PER_STOCK
        )

        state[
            "estimated_operations_used"
        ] = used

        state[
            "stocks_processed"
        ] = (
            state.get(
                "stocks_processed",
                0,
            )
            + 1
        )

        processed_this_run += 1

        # ----------------------------------------------------------
        # RESULT
        # ----------------------------------------------------------

        if result["success"]:

            success += 1

            state[
                "success"
            ] = (
                state.get(
                    "success",
                    0,
                )
                + 1
            )

            print(
                f"        OK "
                f"fundamentals="
                f"{result['fundamentals']} "
                f"market="
                f"{'OK' if result['market'] else 'FAIL'}"
            )

        else:

            failed += 1

            state[
                "failed"
            ] = (
                state.get(
                    "failed",
                    0,
                )
                + 1
            )

            print(
                f"        FAILED "
                f"{result['error']}"
            )

        # ----------------------------------------------------------
        # SAVE AFTER EVERY STOCK
        # ----------------------------------------------------------

        save_state(
            state
        )

        # ----------------------------------------------------------
        # CHECKPOINT
        # ----------------------------------------------------------

        if (
            index
            % CHECKPOINT_EVERY
            == 0
        ):

            print("")

            print(
                "---------------- CHECKPOINT ----------------"
            )

            print(
                f"Processed this run : "
                f"{index:,}"
            )

            print(
                f"Success             : "
                f"{success:,}"
            )

            print(
                f"Failed              : "
                f"{failed:,}"
            )

            print(
                f"Budget used         : "
                f"{used:,}/{USABLE_BUDGET:,}"
            )

            print(
                f"Budget remaining    : "
                f"{USABLE_BUDGET - used:,}"
            )

            print(
                "---------------------------------------------"
            )

            print("")

        # ----------------------------------------------------------
        # DELAY
        # ----------------------------------------------------------

        time.sleep(
            REQUEST_DELAY
        )

    # --------------------------------------------------------------
    # FINAL SAVE
    # --------------------------------------------------------------

    save_state(
        state
    )

    # --------------------------------------------------------------
    # FINAL REPORT
    # --------------------------------------------------------------

    print("")

    print("=" * 90)

    print(
        "NICK V3 — RUN COMPLETE"
    )

    print("=" * 90)

    print("")

    print(
        f"Processed this run        : "
        f"{processed_this_run:,}"
    )

    print(
        f"Success                   : "
        f"{success:,}"
    )

    print(
        f"Failed                    : "
        f"{failed:,}"
    )

    print(
        f"Conservative budget used : "
        f"{used:,}/{USABLE_BUDGET:,}"
    )

    print(
        f"Conservative budget left : "
        f"{USABLE_BUDGET - used:,}"
    )

    print("")

    print(
        "Warehouse counts:"
    )

    for key, value in db.counts().items():

        print(
            f"{key:<25}: {value:,}"
        )

    print("")

    print(
        "State file:"
    )

    print(
        STATE_PATH
    )

    print("")

    print(
        "Next run will automatically resume "
        "from the remaining universe."
    )

    print("")

    print("=" * 90)


if __name__ == "__main__":
    main()


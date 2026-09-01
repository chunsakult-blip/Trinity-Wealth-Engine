"""
Provider-neutral financial fact normalizer.

Responsibilities:
- extract SEC XBRL concepts
- support US-GAAP and IFRS namespaces
- select deterministic facts
- construct canonical financial periods
- normalize CapEx sign convention
- calculate period-level FCF
- calculate true TTM when sufficient data exists
- preserve missing data as None

Important financial semantics:

    Operating Cash Flow != Free Cash Flow

    CapEx is stored as a POSITIVE cash outflow.

    Free Cash Flow = Operating Cash Flow - CapEx

Missing data MUST remain None.
Missing data MUST NOT become zero.
"""

from __future__ import annotations
import re

from datetime import date, timedelta
from typing import Any

from .models import FinancialPeriod, NormalizedFinancials
from .concepts import DEPRECIATION_CANDIDATES, AMORTIZATION_CANDIDATES


class FinancialFactNormalizer:

    # ------------------------------------------------------------------
    # Supported namespaces
    # ------------------------------------------------------------------

    NAMESPACE_PRIORITY = (
        "us-gaap",
        "ifrs-full",
    )

    # ------------------------------------------------------------------
    # Canonical concept registry
    #
    # The normalizer searches all supported namespaces and all aliases.
    # Provider/taxonomy-specific concepts are intentionally kept here
    # instead of leaking into downstream financial engines.
    # ------------------------------------------------------------------

    CONCEPTS = {

        "revenue": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractsWithCustomers",
            "Revenue",
            "Revenues",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
            "SalesRevenueServicesNet",
        ),

        "gross_profit": (
            "GrossProfit",
        ),

        "operating_income": (
            "OperatingIncomeLoss",
            "ProfitLossFromOperatingActivities",
        ),

        "net_income": (
            "NetIncomeLoss",
            "ProfitLoss",
            "ProfitLossAttributableToOwnersOfParent",
            "ProfitLossFromContinuingOperations",
        ),

        "assets": (
            "Assets",
        ),

        "equity": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "PartnersCapital",
            "MemberEquity",
            "Equity",
        ),

        "cash": (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            "CashAndCashEquivalents",
        ),

        "debt": (
            "LongTermDebtCurrent",
            "LongTermDebtNoncurrent",
            "LongTermDebt",
            "LongTermDebtAndFinanceLeaseObligationsCurrent",
            "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
            "ShortTermBorrowings",
            "DebtCurrent",
            "DebtLongtermAndShorttermCombinedAmount",
            "Borrowings",
            "LongtermBorrowings",
            "CurrentPortionOfLongtermBorrowings",
            "ShorttermBorrowings",
        ),

        "operating_cash_flow": (
            "NetCashProvidedByUsedInOperatingActivities",
            "CashFlowsFromUsedInOperatingActivities",
            "CashFlowsFromUsedInOperations",
            "CashFlowsFromUsedInOperatingActivitiesContinuingOperations",
        ),

        # --------------------------------------------------------------
        # CapEx
        #
        # Different issuers/taxonomies may expose capital expenditure
        # under different concepts. All are normalized into one
        # canonical positive cash-outflow value.
        # --------------------------------------------------------------

        "capex": (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
            "PaymentsToAcquireProductiveAssets",
            "PurchaseOfPropertyPlantAndEquipment",
            "PaymentsForPropertyPlantAndEquipment",
            "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssetsClassifiedAsInvestingActivities",
            "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
        ),

        "interest_expense": (
            "InterestExpenseNonOperating",
            "InterestExpenseDebt",
            "InterestExpense",
        ),

        "income_tax_expense": (
            "IncomeTaxExpenseBenefit",
        ),
    }

    DURATION_METRICS = {
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capex",
        "interest_expense",
        "income_tax_expense",
    }

    # ------------------------------------------------------------------
    # Namespace discovery
    # ------------------------------------------------------------------

    @classmethod
    def _available_namespaces(
        cls,
        facts_root: dict[str, Any],
    ) -> list[str]:

        namespaces: list[str] = []

        for namespace in cls.NAMESPACE_PRIORITY:

            data = facts_root.get(namespace)

            if isinstance(data, dict) and data:
                namespaces.append(namespace)

        return namespaces

    # ------------------------------------------------------------------
    # True TTM
    # ------------------------------------------------------------------

    def _build_true_ttm(
        self,
        periods: list[FinancialPeriod],
    ) -> FinancialPeriod | None:

        # ==========================================================
        # Helpers
        # ==========================================================

        def days(period: FinancialPeriod) -> int | None:

            if not period.start or not period.end:
                return None

            try:
                return (
                    date.fromisoformat(period.end)
                    - date.fromisoformat(period.start)
                ).days

            except ValueError:
                return None

        def end_date(
            period: FinancialPeriod,
        ) -> date | None:

            if not period.end:
                return None

            try:
                return date.fromisoformat(period.end)

            except ValueError:
                return None

        def add_day(
            value: str | None,
        ) -> str | None:

            if not value:
                return None

            try:
                return (
                    date.fromisoformat(value)
                    + timedelta(days=1)
                ).isoformat()

            except ValueError:
                return None

        def bridge_value(
            current_ytd: FinancialPeriod,
            previous_ytd: FinancialPeriod,
            previous_fy: FinancialPeriod,
            name: str,
        ) -> float | None:

            current_value = getattr(
                current_ytd,
                name,
                None,
            )

            previous_ytd_value = getattr(
                previous_ytd,
                name,
                None,
            )

            previous_fy_value = getattr(
                previous_fy,
                name,
                None,
            )

            if (
                current_value is None
                or previous_ytd_value is None
                or previous_fy_value is None
            ):
                return None

            return (
                previous_fy_value
                - previous_ytd_value
                + current_value
            )

        # ==========================================================
        # Normalize period collection
        # ==========================================================

        duration = [
            period
            for period in periods
            if days(period) is not None
        ]

        if not duration:
            return None

        # ==========================================================
        # 1. FIND CURRENT YTD
        #
        # SEC YTD periods are normally around 250-300 days.
        #
        # We intentionally use duration rather than exact calendar
        # month/day matching because fiscal calendars can move.
        # ==========================================================

        ytd = [
            period
            for period in duration
            if (
                days(period) is not None
                and 150 <= days(period) <= 300
            )
        ]

        if ytd:

            current_ytd = max(
                ytd,
                key=lambda item: item.end or "",
            )

            current_end = end_date(current_ytd)

            if current_end is not None:

                # ==================================================
                # 2. FIND PRIOR COMPARABLE YTD
                #
                # Requirements:
                #
                # - roughly one fiscal year earlier
                # - similar duration
                # - earlier than current YTD
                #
                # We DO NOT require:
                #
                #     current.end[4:] == prior.end[4:]
                #
                # because Apple can move from 06-28 to 06-27.
                # ==================================================

                current_duration = days(current_ytd)

                prior_ytd_candidates: list[
                    tuple[
                        tuple[int, int, str],
                        FinancialPeriod,
                    ]
                ] = []

                for candidate in ytd:

                    if candidate is current_ytd:
                        continue

                    candidate_end = end_date(candidate)

                    candidate_duration = days(candidate)

                    if (
                        candidate_end is None
                        or candidate_duration is None
                    ):
                        continue

                    if candidate_end >= current_end:
                        continue

                    # Difference between fiscal period ends.
                    year_gap = (
                        current_end - candidate_end
                    ).days

                    # We expect approximately one fiscal year.
                    if not (
                        300 <= year_gap <= 400
                    ):
                        continue

                    duration_gap = abs(
                        candidate_duration
                        - current_duration
                    )

                    # Comparable YTD should have similar duration.
                    if duration_gap > 30:
                        continue

                    score = (
                        duration_gap,
                        abs(year_gap - 365),
                        candidate.end or "",
                    )

                    prior_ytd_candidates.append(
                        (
                            score,
                            candidate,
                        )
                    )

                if prior_ytd_candidates:

                    prior_ytd_candidates.sort(
                        key=lambda item: item[0]
                    )

                    previous_ytd = (
                        prior_ytd_candidates[0][1]
                    )

                    # ==================================================
                    # 3. FIND THE FY THAT CONTAINS PRIOR YTD
                    #
                    # We prefer an annual period whose start matches
                    # the prior YTD start. This is especially important
                    # for companies with non-calendar fiscal years.
                    # ==================================================

                    annual = [
                        period
                        for period in duration
                        if (
                            days(period) is not None
                            and days(period) >= 300
                        )
                    ]

                    previous_ytd_start = (
                        previous_ytd.start
                    )

                    previous_ytd_end = (
                        end_date(previous_ytd)
                    )

                    annual_candidates: list[
                        tuple[
                            tuple[int, int, str],
                            FinancialPeriod,
                        ]
                    ] = []

                    if previous_ytd_end is not None:

                        for candidate in annual:

                            candidate_start = (
                                candidate.start
                            )

                            candidate_end = (
                                end_date(candidate)
                            )

                            if (
                                candidate_start is None
                                or candidate_end is None
                            ):
                                continue

                            # Annual period must contain the prior
                            # YTD period.
                            try:
                                candidate_start_date = (
                                    date.fromisoformat(
                                        candidate_start
                                    )
                                )
                            except ValueError:
                                continue

                            if candidate_start_date > (
                                date.fromisoformat(
                                    previous_ytd.start
                                )
                            ):
                                continue

                            if candidate_end < previous_ytd_end:
                                continue

                            # Must end before current YTD.
                            if candidate_end >= current_end:
                                continue

                            same_start = (
                                0
                                if (
                                    candidate.start
                                    == previous_ytd_start
                                )
                                else 1
                            )

                            end_distance = abs(
                                (
                                    candidate_end
                                    - previous_ytd_end
                                ).days
                            )

                            annual_candidates.append(
                                (
                                    (
                                        same_start,
                                        end_distance,
                                        candidate.end or "",
                                    ),
                                    candidate,
                                )
                            )

                    if annual_candidates:

                        annual_candidates.sort(
                            key=lambda item: item[0]
                        )

                        previous_fy = (
                            annual_candidates[0][1]
                        )

                        # ==================================================
                        # 4. BUILD TRUE TTM USING FISCAL BRIDGE
                        #
                        #       Previous FY
                        #       - Previous YTD
                        #       + Current YTD
                        #
                        # This reconstructs the trailing fiscal year
                        # without requiring standalone Q4.
                        # ==================================================

                        revenue = bridge_value(
                            current_ytd,
                            previous_ytd,
                            previous_fy,
                            "revenue",
                        )

                        if revenue is not None:

                            gross_profit = bridge_value(
                                current_ytd,
                                previous_ytd,
                                previous_fy,
                                "gross_profit",
                            )

                            operating_income = bridge_value(
                                current_ytd,
                                previous_ytd,
                                previous_fy,
                                "operating_income",
                            )

                            net_income = bridge_value(
                                current_ytd,
                                previous_ytd,
                                previous_fy,
                                "net_income",
                            )

                            operating_cash_flow = bridge_value(
                                current_ytd,
                                previous_ytd,
                                previous_fy,
                                "operating_cash_flow",
                            )

                            capex = bridge_value(
                                current_ytd,
                                previous_ytd,
                                previous_fy,
                                "capex",
                            )

                            if capex is not None:
                                capex = abs(capex)

                            free_cash_flow = None

                            if (
                                operating_cash_flow is not None
                                and capex is not None
                            ):
                                free_cash_flow = (
                                    operating_cash_flow
                                    - capex
                                )

                            interest_expense = bridge_value(
                                current_ytd,
                                previous_ytd,
                                previous_fy,
                                "interest_expense",
                            )

                            # ==================================================
                            # ATLAS_CANONICAL_DA_TTM_BRIDGE_V83
                            #
                            # D&A are duration / flow metrics.
                            #
                            # Canonical fiscal bridge:
                            #
                            #       Previous FY
                            #       - Previous YTD
                            #       + Current YTD
                            #
                            # This is the same bridge used by revenue,
                            # operating income, net income, OCF, etc.
                            # ==================================================

                            depreciation = bridge_value(
                                current_ytd,
                                previous_ytd,
                                previous_fy,
                                "depreciation",
                            )

                            amortization = bridge_value(
                                current_ytd,
                                previous_ytd,
                                previous_fy,
                                "amortization",
                            )


                            # The TTM represents the period beginning
                            # immediately after the prior comparable
                            # YTD and ending at the current YTD end.
                            ttm_start = add_day(
                                previous_ytd.end
                            )

                            return FinancialPeriod(

                                period=(
                                    f"TTM:{current_ytd.end}"
                                ),

                                start=ttm_start,

                                end=current_ytd.end,

                                revenue=revenue,

                                gross_profit=gross_profit,

                                operating_income=(
                                    operating_income
                                ),

                                depreciation=depreciation,

                                amortization=amortization,


                                net_income=net_income,

                                assets=current_ytd.assets,

                                equity=current_ytd.equity,

                                cash=current_ytd.cash,

                                debt=current_ytd.debt,

                                operating_cash_flow=(
                                    operating_cash_flow
                                ),

                                capex=capex,

                                free_cash_flow=(
                                    free_cash_flow
                                ),

                                interest_expense=(
                                    interest_expense
                                ),
                            )

        # ==========================================================
        # 5. QUARTERLY FALLBACK
        #
        # Only use this if fiscal YTD bridge could not be constructed.
        #
        # IMPORTANT:
        # Do not blindly take [:4].
        #
        # If standalone Q4 is missing, reconstruct Q4 from:
        #
        #       FY - 9M
        #
        # before assembling the four quarters.
        # ==========================================================

        quarters = [
            period
            for period in duration
            if (
                days(period) is not None
                and 70 <= days(period) <= 110
            )
        ]

        if len(quarters) >= 3:

            quarters_sorted = sorted(
                quarters,
                key=lambda item: item.end or "",
                reverse=True,
            )

            latest_quarter = quarters_sorted[0]

            latest_end = end_date(
                latest_quarter
            )

            if latest_end is not None:

                # Find the latest 3 standalone quarters.
                latest_three = [
                    period
                    for period in quarters_sorted
                    if (
                        end_date(period) is not None
                        and end_date(period) <= latest_end
                    )
                ][:3]

                if len(latest_three) == 3:

                    latest_three = sorted(
                        latest_three,
                        key=lambda item: item.end or "",
                    )

                    # ==================================================
                    # Find a fiscal FY immediately preceding the
                    # latest quarter and its comparable 9M period.
                    # ==================================================

                    annual = [
                        period
                        for period in duration
                        if (
                            days(period) is not None
                            and days(period) >= 300
                            and end_date(period) is not None
                            and end_date(period) < latest_end
                        )
                    ]

                    prior_ytd_candidates = [
                        period
                        for period in ytd
                        if (
                            end_date(period) is not None
                            and end_date(period) < latest_end
                        )
                    ]

                    derived_q4: FinancialPeriod | None = None

                    if annual and prior_ytd_candidates:

                        prior_ytd = max(
                            prior_ytd_candidates,
                            key=lambda item: item.end or "",
                        )

                        prior_ytd_end = end_date(
                            prior_ytd
                        )

                        if prior_ytd_end is not None:

                            containing_fy = [
                                period
                                for period in annual
                                if (
                                    period.start
                                    and period.start
                                    <= prior_ytd.start
                                    and end_date(period)
                                    is not None
                                    and end_date(period)
                                    >= prior_ytd_end
                                )
                            ]

                            if containing_fy:

                                previous_fy = min(
                                    containing_fy,
                                    key=lambda item: abs(
                                        (
                                            end_date(item)
                                            - prior_ytd_end
                                        ).days
                                    ),
                                )

                                q4_revenue = (
                                    bridge_value(
                                        previous_fy,
                                        prior_ytd,
                                        FinancialPeriod(
                                            period="ZERO",
                                            start=None,
                                            end=None,
                                        ),
                                        "revenue",
                                    )
                                    if False
                                    else None
                                )

                                def annual_minus_ytd(
                                    name: str,
                                ) -> float | None:

                                    annual_value = getattr(
                                        previous_fy,
                                        name,
                                        None,
                                    )

                                    ytd_value = getattr(
                                        prior_ytd,
                                        name,
                                        None,
                                    )

                                    if (
                                        annual_value is None
                                        or ytd_value is None
                                    ):
                                        return None

                                    return (
                                        annual_value
                                        - ytd_value
                                    )

                                q4_revenue = (
                                    annual_minus_ytd(
                                        "revenue"
                                    )
                                )

                                if q4_revenue is not None:

                                    q4_gross_profit = (
                                        annual_minus_ytd(
                                            "gross_profit"
                                        )
                                    )

                                    q4_operating_income = (
                                        annual_minus_ytd(
                                            "operating_income"
                                        )
                                    )


                                    q4_net_income = (
                                        annual_minus_ytd(
                                            "net_income"
                                        )
                                    )

                                    # ==================================================
                                    # ATLAS_CANONICAL_Q4_DA_V83
                                    #
                                    # Reconstruct standalone Q4 D&A:
                                    #
                                    #       FY - comparable YTD
                                    # ==================================================


                                    q4_depreciation = (
                                        annual_minus_ytd(
                                            "depreciation"
                                        )
                                    )

                                    q4_amortization = (
                                        annual_minus_ytd(
                                            "amortization"
                                        )
                                    )

                                    q4_ocf = (
                                        annual_minus_ytd(
                                            "operating_cash_flow"
                                        )
                                    )

                                    q4_capex = (
                                        annual_minus_ytd(
                                            "capex"
                                        )
                                    )

                                    if q4_capex is not None:
                                        q4_capex = abs(
                                            q4_capex
                                        )

                                    q4_fcf = None

                                    if (
                                        q4_ocf is not None
                                        and q4_capex is not None
                                    ):
                                        q4_fcf = (
                                            q4_ocf
                                            - q4_capex
                                        )

                                    q4_start = add_day(
                                        prior_ytd.end
                                    )

                                    derived_q4 = (
                                        FinancialPeriod(
                                            period=(
                                                "Q4:"
                                                f"{previous_fy.end}"
                                            ),
                                            start=q4_start,
                                            end=previous_fy.end,
                                            revenue=q4_revenue,
                                            gross_profit=(
                                                q4_gross_profit
                                            ),
                                            operating_income=(
                                                q4_operating_income
                                            ),

                                            depreciation=(
                                                q4_depreciation
                                            ),
                                            amortization=(
                                                q4_amortization
                                            ),
                                            net_income=(
                                                q4_net_income
                                            ),
                                            assets=previous_fy.assets,
                                            equity=previous_fy.equity,
                                            cash=previous_fy.cash,
                                            debt=previous_fy.debt,
                                            operating_cash_flow=q4_ocf,
                                            capex=q4_capex,
                                            free_cash_flow=q4_fcf,
                                            interest_expense=(
                                                annual_minus_ytd(
                                                    "interest_expense"
                                                )
                                            ),
                                        )
                                    )

                    # ==================================================
                    # Assemble quarterly TTM.
                    #
                    # CASE A:
                    # Four complete standalone quarters already exist.
                    # Sum them directly.
                    #
                    # CASE B:
                    # Only three standalone quarters exist.
                    # Use reconstructed FY - prior YTD Q4 when available.
                    #
                    # This is critical because a payload containing
                    # exactly four standalone quarters must NOT depend
                    # on a derived Q4.
                    # ==================================================

                    if len(latest_three) == 3:

                        direct_four_quarters = (
                            derived_q4 is None
                            and len(quarters_sorted) >= 4
                        )

                        if direct_four_quarters:

                            direct_qs = sorted(
                                quarters_sorted[:4],
                                key=lambda item: item.end or "",
                            )

                            latest = direct_qs[-1]

                            def sum_direct_complete(
                                name: str,
                            ) -> float | None:

                                values = [
                                    getattr(
                                        item,
                                        name,
                                        None,
                                    )
                                    for item in direct_qs
                                ]

                                if any(
                                    value is None
                                    for value in values
                                ):
                                    return None

                                return sum(values)

                            revenue = sum_direct_complete(
                                "revenue"
                            )

                            if revenue is not None:

                                gross_profit = (
                                    sum_direct_complete(
                                        "gross_profit"
                                    )
                                )

                                operating_income = (
                                    sum_direct_complete(
                                        "operating_income"
                                    )
                                )

                                net_income = (
                                    sum_direct_complete(
                                        "net_income"
                                    )
                                )

                                depreciation = (
                                    sum_direct_complete(
                                        "depreciation"
                                    )
                                )

                                amortization = (
                                    sum_direct_complete(
                                        "amortization"
                                    )
                                )

                                operating_cash_flow = (
                                    sum_direct_complete(
                                        "operating_cash_flow"
                                    )
                                )

                                capex = (
                                    sum_direct_complete(
                                        "capex"
                                    )
                                )

                                if capex is not None:
                                    capex = abs(capex)

                                free_cash_flow = None

                                if (
                                    operating_cash_flow
                                    is not None
                                    and capex is not None
                                ):
                                    free_cash_flow = (
                                        operating_cash_flow
                                        - capex
                                    )

                                interest_expense = (
                                    sum_direct_complete(
                                        "interest_expense"
                                    )
                                )

                                return FinancialPeriod(

                                    period=(
                                        f"TTM:{latest.end}"
                                    ),

                                    start=direct_qs[0].start,

                                    end=latest.end,

                                    revenue=revenue,

                                    gross_profit=(
                                        gross_profit
                                    ),

                                    operating_income=(
                                        operating_income
                                    ),

                                    depreciation=depreciation,

                                    amortization=amortization,

                                    net_income=net_income,

                                    assets=latest.assets,

                                    equity=latest.equity,

                                    cash=latest.cash,

                                    debt=latest.debt,

                                    operating_cash_flow=(
                                        operating_cash_flow
                                    ),

                                    capex=capex,

                                    free_cash_flow=(
                                        free_cash_flow
                                    ),

                                    interest_expense=(
                                        interest_expense
                                    ),
                                )

                    # ==================================================
                    # Reconstructed-Q4 path.
                    #
                    # Only use this when standalone Q4 is absent.
                    # ==================================================

                    if derived_q4 is not None:

                        qs = [
                            derived_q4,
                            *latest_three,
                        ]

                        qs = sorted(
                            qs,
                            key=lambda item: item.end or "",
                        )

                        latest = qs[-1]

                        def sum_complete(
                            name: str,
                        ) -> float | None:

                            values = [
                                getattr(
                                    item,
                                    name,
                                    None,
                                )
                                for item in qs
                            ]

                            if any(
                                value is None
                                for value in values
                            ):
                                return None

                            return sum(values)

                        revenue = sum_complete(
                            "revenue"
                        )

                        if revenue is not None:

                            gross_profit = sum_complete(
                                "gross_profit"
                            )

                            operating_income = sum_complete(
                                "operating_income"
                            )

                            net_income = sum_complete(
                                "net_income"
                            )

                            depreciation = sum_complete(
                                "depreciation"
                            )

                            amortization = sum_complete(
                                "amortization"
                            )

                            operating_cash_flow = (
                                sum_complete(
                                    "operating_cash_flow"
                                )
                            )

                            capex = sum_complete(
                                "capex"
                            )

                            if capex is not None:
                                capex = abs(capex)

                            free_cash_flow = None

                            if (
                                operating_cash_flow
                                is not None
                                and capex is not None
                            ):
                                free_cash_flow = (
                                    operating_cash_flow
                                    - capex
                                )

                            interest_expense = (
                                sum_complete(
                                    "interest_expense"
                                )
                            )

                            return FinancialPeriod(

                                period=(
                                    f"TTM:{latest.end}"
                                ),

                                start=qs[0].start,

                                end=latest.end,

                                revenue=revenue,

                                gross_profit=(
                                    gross_profit
                                ),

                                operating_income=(
                                    operating_income
                                ),

                                depreciation=depreciation,

                                amortization=amortization,

                                net_income=net_income,

                                assets=latest.assets,

                                equity=latest.equity,

                                cash=latest.cash,

                                debt=latest.debt,

                                operating_cash_flow=(
                                    operating_cash_flow
                                ),

                                capex=capex,

                                free_cash_flow=(
                                    free_cash_flow
                                ),

                                interest_expense=(
                                    interest_expense
                                ),
                            )

                        qs = [
                            derived_q4,
                            *latest_three,
                        ]

                        qs = sorted(
                            qs,
                            key=lambda item: item.end or "",
                        )

                        latest = qs[-1]

                        def sum_complete(
                            name: str,
                        ) -> float | None:

                            values = [
                                getattr(
                                    item,
                                    name,
                                    None,
                                )
                                for item in qs
                            ]

                            if any(
                                value is None
                                for value in values
                            ):
                                return None

                            return sum(values)

                        revenue = sum_complete(
                            "revenue"
                        )

                        if revenue is not None:

                            gross_profit = sum_complete(
                                "gross_profit"
                            )

                            operating_income = sum_complete(
                                "operating_income"
                            )

                            net_income = sum_complete(
                                "net_income"
                            )

                            operating_cash_flow = (
                                sum_complete(
                                    "operating_cash_flow"
                                )
                            )

                            capex = sum_complete(
                                "capex"
                            )

                            if capex is not None:
                                capex = abs(capex)

                            free_cash_flow = None

                            if (
                                operating_cash_flow
                                is not None
                                and capex is not None
                            ):
                                free_cash_flow = (
                                    operating_cash_flow
                                    - capex
                                )

                            interest_expense = (
                                sum_complete(
                                    "interest_expense"
                                )
                            )

                            return FinancialPeriod(

                                period=(
                                    f"TTM:{latest.end}"
                                ),

                                start=qs[0].start,

                                end=latest.end,

                                revenue=revenue,

                                gross_profit=gross_profit,

                                operating_income=(
                                    operating_income
                                ),

                                net_income=net_income,

                                assets=latest.assets,

                                equity=latest.equity,

                                cash=latest.cash,

                                debt=latest.debt,

                                operating_cash_flow=(
                                    operating_cash_flow
                                ),

                                capex=capex,

                                free_cash_flow=(
                                    free_cash_flow
                                ),

                                interest_expense=(
                                    interest_expense
                                ),
                            )

        # ==========================================================
        # 6. ANNUAL FALLBACK
        #
        # If YTD data exists but cannot construct a true TTM,
        # do not fabricate TTM from an annual period.
        # ==========================================================

        if ytd:
            return None

        annual = [
            period
            for period in duration
            if (
                days(period) is not None
                and days(period) >= 300
            )
        ]

        if annual:

            period = max(
                annual,
                key=lambda item: item.end or "",
            )

            free_cash_flow = None

            if (
                period.operating_cash_flow is not None
                and period.capex is not None
            ):
                free_cash_flow = (
                    period.operating_cash_flow
                    - abs(period.capex)
                )

            return FinancialPeriod(

                period=f"TTM:{period.end}",

                start=period.start,

                end=period.end,

                revenue=period.revenue,

                gross_profit=period.gross_profit,


                depreciation=(
                    period.depreciation
                    if period.depreciation is not None
                    else None
                ),

                amortization=(
                    period.amortization
                    if period.amortization is not None
                    else None
                ),
                operating_income=period.operating_income,

                net_income=period.net_income,

                assets=period.assets,

                equity=period.equity,

                cash=period.cash,

                debt=period.debt,

                operating_cash_flow=(
                    period.operating_cash_flow
                ),

                capex=(
                    abs(period.capex)
                    if period.capex is not None
                    else None
                ),

                free_cash_flow=free_cash_flow,

                interest_expense=(
                    period.interest_expense
                ),
            )

        return None

    # ------------------------------------------------------------------
    # Public normalization API
    # ------------------------------------------------------------------

    def _normalize_raw(
        self,
        payload: dict[str, Any],
        *,
        cik: int,
        ticker: str | None = None,
        company_name: str | None = None,
    ) -> NormalizedFinancials:

        if not isinstance(payload, dict):
            raise TypeError(
                "SEC Company Facts payload must be a dict."
            )

        entity_name = (
            company_name
            or payload.get("entityName")
            or ""
        )

        facts_root = payload.get(
            "facts",
            {},
        )

        if not isinstance(facts_root, dict):
            raise ValueError(
                "SEC Company Facts payload missing facts."
            )

        namespaces = self._available_namespaces(
            facts_root
        )

        if not namespaces:
            raise ValueError(
                "SEC Company Facts payload contains neither "
                "us-gaap nor ifrs-full facts."
            )

        concept_values: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        evidence: list[dict[str, Any]] = []

        # --------------------------------------------------------------
        # EXTRACT
        # --------------------------------------------------------------

        for metric_name, concepts in self.CONCEPTS.items():

            values: list[dict[str, Any]] = []

            for namespace in namespaces:

                namespace_data = facts_root.get(
                    namespace,
                    {},
                )

                if not isinstance(
                    namespace_data,
                    dict,
                ):
                    continue

                for concept_priority, concept in enumerate(
                    concepts
                ):

                    node = namespace_data.get(
                        concept
                    )

                    if not isinstance(
                        node,
                        dict,
                    ):
                        continue

                    units = node.get(
                        "units",
                        {},
                    )

                    if not isinstance(
                        units,
                        dict,
                    ):
                        continue

                    for unit, entries in units.items():

                        if not isinstance(
                            entries,
                            list,
                        ):
                            continue

                        for entry in entries:

                            if not isinstance(
                                entry,
                                dict,
                            ):
                                continue

                            value = entry.get(
                                "val"
                            )

                            end = entry.get(
                                "end"
                            )

                            if (
                                value is None
                                or end is None
                            ):
                                continue

                            item = dict(entry)

                            item["_concept"] = concept
                            item["_unit"] = unit
                            item["_namespace"] = namespace
                            item["_concept_priority"] = (
                                concept_priority
                            )

                            values.append(item)

            # ==========================================================
            # ATLAS — CANONICAL CONCEPT INDEX
            #
            # The generic normalizer stores facts primarily under
            # metric_name. D&A selection, however, operates on SEC
            # concept names.
            #
            # Therefore expose the same SEC facts under:
            #
            #   1. bare concept name
            #   2. namespace:concept name
            #
            # Also normalize SEC "val" into the canonical "value"
            # field expected by the D&A selector.
            # ==========================================================

            for item in values:

                concept_name = item.get(
                    "_concept"
                )

                namespace_name = item.get(
                    "_namespace"
                )

                if concept_name:

                    item["value"] = item.get(
                        "val"
                    )

                    concept_bucket = concept_values.setdefault(
                        concept_name,
                        [],
                    )

                    concept_bucket.append(
                        item
                    )

                    if namespace_name:

                        namespaced_key = (
                            f"{namespace_name}:{concept_name}"
                        )

                        namespaced_bucket = concept_values.setdefault(
                            namespaced_key,
                            [],
                        )

                        namespaced_bucket.append(
                            item
                        )

            concept_values[metric_name] = values

            if values:

                evidence.append(
                    {
                        "type": "sec_xbrl",
                        "metric": metric_name,
                        "namespaces": sorted(
                            {
                                item["_namespace"]
                                for item in values
                            }
                        ),
                        "concepts": sorted(
                            {
                                item["_concept"]
                                for item in values
                            }
                        ),
                        "count": len(values),
                    }
                )


        # ==============================================================
        # ATLAS_DA_SOURCE_POPULATION_V57
        #
        # Directly expose canonical SEC D&A concepts to concept_values.
        # RAW SEC facts are known to exist; this repairs only the
        # source-population boundary.
        # ==============================================================

        _atlas_da_concepts = (
            "DepreciationAndAmortization",
            "DepreciationDepletionAndAmortization",
            "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
            "Depreciation",
            "DepreciationExpense",
            "AmortizationOfIntangibleAssets",
            "AmortizationExpense",
            "AmortizationOfIntangibleAssetsExcludingGoodwill",
            "Amortization",
        )

        try:
            _atlas_facts = payload.get("facts", {})
        except AttributeError:
            _atlas_facts = {}

        if isinstance(_atlas_facts, dict):

            _atlas_us_gaap = _atlas_facts.get(
                "us-gaap",
                {},
            )

            if isinstance(_atlas_us_gaap, dict):

                for _atlas_concept in _atlas_da_concepts:

                    _atlas_node = _atlas_us_gaap.get(
                        _atlas_concept
                    )

                    if not isinstance(
                        _atlas_node,
                        dict,
                    ):
                        continue

                    _atlas_units = _atlas_node.get(
                        "units",
                        {},
                    )

                    if not isinstance(
                        _atlas_units,
                        dict,
                    ):
                        continue

                    _atlas_values = []

                    for _atlas_unit, _atlas_entries in _atlas_units.items():

                        if not isinstance(
                            _atlas_entries,
                            list,
                        ):
                            continue

                        for _atlas_entry in _atlas_entries:

                            if not isinstance(
                                _atlas_entry,
                                dict,
                            ):
                                continue

                            if (
                                _atlas_entry.get("val") is None
                                or _atlas_entry.get("end") is None
                            ):
                                continue

                            _atlas_item = dict(
                                _atlas_entry
                            )

                            _atlas_item["_concept"] = (
                                _atlas_concept
                            )

                            _atlas_item["_unit"] = (
                                _atlas_unit
                            )

                            _atlas_item["_namespace"] = (
                                "us-gaap"
                            )

                            _atlas_values.append(
                                _atlas_item
                            )

                    if _atlas_values:

                        concept_values[
                            _atlas_concept
                        ] = _atlas_values

                        concept_values[
                            "us-gaap:" + _atlas_concept
                        ] = _atlas_values


        # --------------------------------------------------------------
        # DETERMINISTIC FACT SELECTION
        # --------------------------------------------------------------

        def select_value(
            metric_name: str,
            *,
            duration: bool,
            end_date: str | None = None,
            start_date: str | None = None,
        ) -> float | None:

            values = concept_values.get(
                metric_name,
                [],
            )

            candidates: list[
                tuple[
                    tuple[Any, ...],
                    float,
                ]
            ] = []

            for item in values:

                value = item.get("val")
                end = item.get("end")

                if (
                    value is None
                    or end is None
                ):
                    continue

                if (
                    end_date is not None
                    and end != end_date
                ):
                    continue

                if (
                    start_date is not None
                    and item.get("start") != start_date
                ):
                    continue

                start = item.get("start")

                duration_days = 0

                if start and end:

                    try:
                        duration_days = (
                            date.fromisoformat(end)
                            - date.fromisoformat(start)
                        ).days

                    except ValueError:
                        duration_days = 0

                form = str(
                    item.get(
                        "form",
                        "",
                    )
                ).upper()

                fp = str(
                    item.get(
                        "fp",
                        "",
                    )
                ).upper()

                annual_preference = (
                    1
                    if (
                        duration
                        and duration_days >= 300
                    )
                    else 0
                )

                fy_preference = (
                    1
                    if fp == "FY"
                    else 0
                )

                form_preference = (
                    1
                    if form in {
                        "10-K",
                        "10-K/A",
                        "20-F",
                        "20-F/A",
                        "40-F",
                        "40-F/A",
                    }
                    else 0
                )

                filed = str(
                    item.get(
                        "filed",
                        "",
                    )
                )

                namespace_priority = (
                    len(self.NAMESPACE_PRIORITY)
                    - self.NAMESPACE_PRIORITY.index(
                        item.get(
                            "_namespace",
                            "",
                        )
                    )
                    if item.get("_namespace")
                    in self.NAMESPACE_PRIORITY
                    else 0
                )

                concept_priority = -int(
                    item.get(
                        "_concept_priority",
                        999,
                    )
                )

                score = (
                    end,
                    annual_preference,
                    fy_preference,
                    form_preference,
                    namespace_priority,
                    filed,
                    concept_priority,
                )

                try:
                    numeric_value = float(
                        value
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                candidates.append(
                    (
                        score,
                        numeric_value,
                    )
                )

            if not candidates:
                return None

            candidates.sort(
                key=lambda item: item[0]
            )

            return candidates[-1][1]

        # --------------------------------------------------------------
        # DISCOVER PERIOD KEYS
        # --------------------------------------------------------------

        period_keys: set[
            tuple[
                str | None,
                str | None,
            ]
        ] = set()

        for values in concept_values.values():

            for item in values:

                start = item.get("start")
                end = item.get("end")

                if not end:
                    continue

                period_keys.add(
                    (
                        start,
                        end,
                    )
                )

        # --------------------------------------------------------------
        # REMOVE DUPLICATE INSTANT PERIODS
        # --------------------------------------------------------------

        duration_ends = {
            end
            for start, end in period_keys
            if (
                start is not None
                and end is not None
            )
        }

        deduplicated_keys = {
            (
                start,
                end,
            )
            for start, end in period_keys
            if not (
                start is None
                and end in duration_ends
            )
        }

        ordered_keys = sorted(
            deduplicated_keys,
            key=lambda item: (
                item[1] or "",
                item[0] or "",
            ),
            reverse=True,
        )

        # --------------------------------------------------------------
        # BUILD CANONICAL PERIODS
        # --------------------------------------------------------------

        periods: list[
            FinancialPeriod
        ] = []

        for start, end in ordered_keys:

            if not end:
                continue

            period_name = (
                f"{start}:{end}"
                if start
                else end
            )

            period = FinancialPeriod(

                period=period_name,

                start=start,
                end=end,

                revenue=select_value(
                    "revenue",
                    duration=True,
                    end_date=end,
                    start_date=start,
                ),

                gross_profit=select_value(
                    "gross_profit",
                    duration=True,
                    end_date=end,
                    start_date=start,
                ),

                operating_income=select_value(
                    "operating_income",
                    duration=True,
                    end_date=end,
                    start_date=start,
                ),

                # ============================================================
                # ATLAS_CANONICAL_DA_PERIOD_WIRING_V3
                #
                # Direct SEC concept_values selector.
                #
                # IMPORTANT:
                #   D&A is a duration / flow metric.
                #   It must therefore use the same start/end period as the
                #   FinancialPeriod being constructed.
                # ============================================================

                depreciation=_atlas_extract_da_value(
                    concept_values,
                    DEPRECIATION_CANDIDATES,
                    start_date=start,
                    end_date=end,
                ),

                amortization=_atlas_extract_da_value(
                    concept_values,
                    AMORTIZATION_CANDIDATES,
                    start_date=start,
                    end_date=end,
                ),

                net_income=select_value(
                    "net_income",
                    duration=True,
                    end_date=end,
                    start_date=start,
                ),

                assets=select_value(
                    "assets",
                    duration=False,
                    end_date=end,
                ),

                equity=select_value(
                    "equity",
                    duration=False,
                    end_date=end,
                ),

                cash=select_value(
                    "cash",
                    duration=False,
                    end_date=end,
                ),

                debt=select_value(
                    "debt",
                    duration=False,
                    end_date=end,
                ),

                operating_cash_flow=select_value(
                    "operating_cash_flow",
                    duration=True,
                    end_date=end,
                    start_date=start,
                ),

                capex=select_value(
                    "capex",
                    duration=True,
                    end_date=end,
                    start_date=start,
                ),

                interest_expense=select_value(
                    "interest_expense",
                    duration=True,
                    end_date=end,
                    start_date=start,
                ),
            )

            # ----------------------------------------------------------
            # Canonical CapEx sign
            # ----------------------------------------------------------

            if period.capex is not None:
                period.capex = abs(
                    period.capex
                )

            # ----------------------------------------------------------
            # Canonical FCF
            #
            # Missing CapEx MUST remain missing.
            # ----------------------------------------------------------

            period.free_cash_flow = None

            if (
                period.operating_cash_flow is not None
                and period.capex is not None
            ):
                period.free_cash_flow = (
                    period.operating_cash_flow
                    - period.capex
                )

            # Keep a period if at least one meaningful
            # financial fact exists.
            if any(
                value is not None
                for value in (
                    period.revenue,
                    period.net_income,
                    period.assets,
                    period.equity,
                    period.operating_cash_flow,
                    period.capex,
                )
            ):
                periods.append(
                    period
                )

        # ============================================================
        # V83 — BUILD CANONICAL TRUE TTM
        #
        # IMPORTANT:
        # periods is now fully constructed.
        #
        # The canonical TTM builder must run here so that:
        #
        #     NormalizedFinancials.ttm
        #
        # receives the actual True TTM period.
        #
        # Do NOT calculate TTM from periods[-4:].
        # Do NOT duplicate the fiscal bridge here.
        # _build_true_ttm() is the single canonical implementation.
        # ============================================================

        true_ttm = self._build_true_ttm(
            periods
        )

        # --------------------------------------------------------------
        # LATEST / PRIOR
        # --------------------------------------------------------------

        latest_period = (
            periods[0]
            if periods
            else None
        )

        prior_period = (
            periods[1]
            if len(periods) > 1
            else None
        )

        latest_end = (
            latest_period.end
            if latest_period
            else None
        )

        # --------------------------------------------------------------
        # BASE METRICS
        # --------------------------------------------------------------

        metrics: dict[
            str,
            float | None,
        ] = {}

        for metric_name in self.CONCEPTS:

            metrics[metric_name] = select_value(
                metric_name,
                duration=(
                    metric_name
                    in self.DURATION_METRICS
                ),
                end_date=latest_end,
                start_date=(
                    latest_period.start
                    if (
                        latest_period
                        and metric_name
                        in self.DURATION_METRICS
                    )
                    else None
                ),
            )

        if latest_period is not None:

            metrics["free_cash_flow"] = (
                latest_period.free_cash_flow
            )

        else:

            metrics["free_cash_flow"] = None

        # --------------------------------------------------------------
        # TAX RATE
        # --------------------------------------------------------------

        income_tax = metrics.get(
            "income_tax_expense"
        )

        net_income = metrics.get(
            "net_income"
        )

        if (
            income_tax is not None
            and net_income is not None
        ):

            pretax_income = (
                net_income
                + income_tax
            )

            if pretax_income > 0:

                metrics["tax_rate"] = (
                    income_tax
                    / pretax_income
                )

            else:

                metrics["tax_rate"] = None

        else:

            metrics["tax_rate"] = None


        # --------------------------------------------------------------
        # TRUE TTM

        # ============================================================
        # V83 — CANONICAL D&A TTM
        #
        # D&A are now calculated directly by _build_true_ttm().
        #
        # Fiscal bridge:
        #     Previous FY - Previous YTD + Current YTD
        #
        # Quarterly fallback:
        #     Q4 = FY - comparable YTD
        #
        # Do NOT use periods[-4:] because the period collection may
        # contain FY / YTD / quarterly mixtures.
        # ============================================================

        # --------------------------------------------------------------
        # Currency detection
        #
        # Prefer the unit associated with revenue.
        # This avoids hard-coding USD for IFRS companies.
        # --------------------------------------------------------------

        currency = None

        revenue_values = concept_values.get(
            "revenue",
            [],
        )

        if revenue_values:

            latest_revenue = sorted(
                revenue_values,
                key=lambda item: (
                    str(
                        item.get(
                            "end",
                            "",
                        )
                    ),
                    str(
                        item.get(
                            "filed",
                            "",
                        )
                    ),
                ),
                reverse=True,
            )[0]

            currency = latest_revenue.get(
                "_unit"
            )

        return NormalizedFinancials(

            cik=cik,

            ticker=ticker,

            company_name=entity_name,

            currency=currency,

            latest_period=latest_period,

            prior_period=prior_period,

            ttm=true_ttm,

            periods=periods,

            metrics=metrics,

            quality={},

            evidence=evidence,
        )





# ============================================================
# ATLAS_CANONICAL_DA_SELECTOR_V2
#
# Direct SEC concept_values selector for depreciation /
# amortization.
#
# Strategy:
#   1. exact start/end duration match
#   2. same-end duration match
#   3. choose latest filed fact
#
# This intentionally operates on concept_values because the
# existing generic selector is not producing usable D&A facts.
# ============================================================



def _atlas_select_da_from_concept_values(
    concept_values,
    candidates,
    *,
    start_date=None,
    end_date=None,
):
    """
    ATLAS canonical D&A selector V65.

    Selection order:

      1. exact concept match
      2. exact duration: start + end
      3. same-end duration
      4. containing duration
      5. latest valid duration ending on/before requested end

    SEC XBRL rows normally use "val", while some internal test
    representations use "value". Both are supported.
    """

    if not isinstance(
        concept_values,
        dict,
    ):
        return None

    # --------------------------------------------------------
    # Candidate concept normalization.
    # --------------------------------------------------------

    candidate_names = []

    for candidate in candidates or []:

        if candidate is None:
            continue

        name = str(candidate).strip()

        if not name:
            continue

        candidate_names.append(name)

        if name.startswith("us-gaap:"):

            candidate_names.append(
                name.split(
                    ":",
                    1,
                )[1]
            )

        else:

            candidate_names.append(
                "us-gaap:" + name
            )

    def normalize_concept_name(value):

        value = str(
            value or ""
        ).strip()

        if ":" in value:

            value = value.split(
                ":",
                1,
            )[1]

        return re.sub(
            r"[^a-z0-9]",
            "",
            value.lower(),
        )

    normalized_candidates = {
        normalize_concept_name(x)
        for x in candidate_names
    }

    # --------------------------------------------------------
    # Date normalization.
    # --------------------------------------------------------

    def clean_date(value):

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        return value[:10]

    requested_start = clean_date(
        start_date
    )

    requested_end = clean_date(
        end_date
    )

    # --------------------------------------------------------
    # Numeric extraction.
    # --------------------------------------------------------

    def extract_numeric(row):

        if not isinstance(
            row,
            dict,
        ):
            return None

        # SEC live shape is "val".
        # Internal compatibility shape may be "value".
        for key in (
            "val",
            "value",
            "numeric_value",
            "amount",
            "raw_value",
            "number",
        ):

            if key not in row:
                continue

            raw = row.get(key)

            if raw is None:
                continue

            if isinstance(
                raw,
                bool,
            ):
                continue

            try:
                return float(raw)

            except (
                TypeError,
                ValueError,
            ):
                continue

        return None

    # --------------------------------------------------------
    # Collect candidate rows.
    # --------------------------------------------------------

    values = []

    for concept_key, rows in concept_values.items():

        normalized_key = normalize_concept_name(
            concept_key
        )

        if normalized_key not in normalized_candidates:
            continue

        if isinstance(
            rows,
            list,
        ):

            iterable = rows

        elif isinstance(
            rows,
            dict,
        ):

            if isinstance(
                rows.get("facts"),
                list,
            ):

                iterable = rows["facts"]

            elif isinstance(
                rows.get("values"),
                list,
            ):

                iterable = rows["values"]

            elif isinstance(
                rows.get("data"),
                list,
            ):

                iterable = rows["data"]

            else:

                iterable = [rows]

        else:
            continue

        for row in iterable:

            if not isinstance(
                row,
                dict,
            ):
                continue

            value = extract_numeric(
                row
            )

            if value is None:
                continue

            row_end = clean_date(
                row.get("end")
            )

            if row_end is None:
                continue

            row_start = clean_date(
                row.get("start")
            )

            # D&A is a duration fact.
            # Reject instant-only facts.
            if row_start is None:
                continue

            values.append(
                {
                    "value": value,
                    "start": row_start,
                    "end": row_end,
                    "filed": str(
                        row.get("filed")
                        or ""
                    ),
                    "form": str(
                        row.get("form")
                        or ""
                    ),
                    "fp": str(
                        row.get("fp")
                        or ""
                    ),
                    "fy": str(
                        row.get("fy")
                        or ""
                    ),
                    "concept": str(
                        concept_key
                    ),
                }
            )

    if not values:
        return None

    # --------------------------------------------------------
    # Date helper.
    # --------------------------------------------------------

    def is_between(
        value,
        lower,
        upper,
    ):

        if (
            value is None
            or lower is None
            or upper is None
        ):
            return False

        return (
            lower
            <= value
            <= upper
        )

    # --------------------------------------------------------
    # 1. EXACT DURATION
    # --------------------------------------------------------

    if (
        requested_start is not None
        and requested_end is not None
    ):

        exact = [
            row
            for row in values
            if (
                row["start"]
                == requested_start
                and row["end"]
                == requested_end
            )
        ]

        if exact:

            exact.sort(
                key=lambda row: (
                    row["filed"],
                    row["form"],
                    row["concept"],
                ),
                reverse=True,
            )

            return exact[0]["value"]

    # --------------------------------------------------------
    # 2. SAME END DATE
    #
    # Prefer a duration whose end matches the requested end.
    # Among those, prefer the closest start date.
    # --------------------------------------------------------

    if requested_end is not None:

        same_end = [
            row
            for row in values
            if row["end"] == requested_end
        ]

        if requested_start is not None:

            same_end = [
                row
                for row in same_end
                if row["start"] <= requested_start
            ]

        if same_end:

            same_end.sort(
                key=lambda row: (
                    row["start"],
                    row["filed"],
                    row["form"],
                ),
                reverse=True,
            )

            return same_end[0]["value"]

    # --------------------------------------------------------
    # 3. CONTAINING DURATION
    #
    # Requested window must sit inside the SEC duration.
    # --------------------------------------------------------

    if (
        requested_start is not None
        and requested_end is not None
    ):

        containing = [
            row
            for row in values
            if (
                row["start"]
                <= requested_start
                and row["end"]
                >= requested_end
            )
        ]

        if containing:

            containing.sort(
                key=lambda row: (
                    row["start"],
                    row["end"],
                    row["filed"],
                    row["form"],
                ),
                reverse=True,
            )

            return containing[0]["value"]

    # --------------------------------------------------------
    # 4. LATEST VALID DURATION
    #
    # Last deterministic fallback.
    # --------------------------------------------------------

    if requested_end is not None:

        prior = [
            row
            for row in values
            if row["end"] <= requested_end
        ]

        if prior:

            prior.sort(
                key=lambda row: (
                    row["end"],
                    row["start"],
                    row["filed"],
                    row["form"],
                ),
                reverse=True,
            )

            return prior[0]["value"]

    # --------------------------------------------------------
    # 5. No requested dates.
    #
    # Return latest filed duration fact.
    # --------------------------------------------------------

    values.sort(
        key=lambda row: (
            row["end"],
            row["filed"],
            row["start"],
        ),
        reverse=True,
    )

    return values[0]["value"]

def _atlas_extract_da_value(
    concept_values,
    candidates,
    *,
    start_date=None,
    end_date=None,
):
    return _atlas_select_da_from_concept_values(
        concept_values,
        candidates,
        start_date=start_date,
        end_date=end_date,
    )


# ============================================================
# ATLAS_TTM_METRICS_SEMANTICS_PATCH_V1
#
# Canonical downstream metric projection.
#
# IMPORTANT:
#   - Flow metrics MUST use TRUE TTM.
#   - Balance-sheet metrics MUST use latest snapshot.
#   - Growth MUST use comparable TTM periods.
#
# The underlying TTM construction remains untouched.
# ============================================================

def _atlas_days_between(start, end):
    if not start or not end:
        return None

    try:
        a = date.fromisoformat(str(start))
        b = date.fromisoformat(str(end))
        return (b - a).days + 1
    except Exception:
        return None


def _atlas_find_prior_ttm(periods, current_ttm):
    """
    Return the prior comparable TTM.

    IMPORTANT:
        `periods` contains raw SEC duration periods and instant
        periods.  A raw FY is NOT necessarily the prior TTM.

    Canonical comparison:

        Current TTM
            vs
        Prior Comparable TTM

    For an interim TTM, reconstruct:

        Prior TTM =
            Prior FY
            - Older Comparable YTD
            + Prior Comparable YTD

    Example:

        Current TTM:
            2025-07-01 -> 2026-06-30

        Prior Comparable TTM:
            2024-07-01 -> 2025-06-30

        reconstructed from:

            FY 2024
            - YTD 2024
            + YTD 2025
    """

    if current_ttm is None:
        return None

    # ------------------------------------------------------------
    # NORMALIZE OBJECT / DICT ACCESS
    #
    # The production pipeline normally passes FinancialPeriod.
    # Validation and some adapter paths may pass a dict-shaped
    # representation of the TTM.
    #
    # Support both without changing the canonical FinancialPeriod
    # model or upstream callers.
    # ------------------------------------------------------------

    def _get(obj, key, default=None):
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    current_start = _get(
        current_ttm,
        "start",
        None,
    )

    current_end = _get(
        current_ttm,
        "end",
        None,
    )

    if not current_end:
        return None

    try:
        current_end_date = date.fromisoformat(
            str(current_end)
        )
    except Exception:
        return None

    def _date(value):
        if not value:
            return None

        try:
            return date.fromisoformat(
                str(value)
            )
        except Exception:
            return None

    def _days(period):
        start = _date(
            _get(period, "start", None)
        )
        end = _date(
            _get(period, "end", None)
        )

        if start is None or end is None:
            return None

        return (end - start).days + 1

    def _duration(period):
        value = _days(period)

        if value is None:
            return None

        return value

    def _same_period(a, b):
        if a is None or b is None:
            return False

        return (
            getattr(a, "start", None)
            == getattr(b, "start", None)
            and
            getattr(a, "end", None)
            == getattr(b, "end", None)
        )

    all_periods = [
        p
        for p in (periods or [])
        if (
            getattr(p, "start", None)
            and
            getattr(p, "end", None)
        )
    ]

    if not all_periods:
        return None

    # --------------------------------------------------------
    # FLOW FIELDS
    # --------------------------------------------------------

    flow_fields = (
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capex",
        "free_cash_flow",
        "interest_expense",
        "depreciation",
        "amortization",
    )

    # --------------------------------------------------------
    # IDENTIFY LIKELY YTD PERIODS
    #
    # We deliberately do NOT classify a period as YTD solely
    # from its exact calendar dates.  Fiscal calendars vary.
    #
    # The selector therefore uses duration + temporal
    # relationship to the current TTM.
    # --------------------------------------------------------

    candidates = []

    for period in all_periods:

        if _same_period(period, current_ttm):
            continue

        start = _date(
            _get(period, "start", None)
        )

        end = _date(
            _get(period, "end", None)
        )

        days = _duration(period)

        if (
            start is None
            or end is None
            or days is None
        ):
            continue

        if end >= current_end_date:
            continue

        # Ignore very short quarterly periods.
        #
        # A YTD is normally materially longer than a quarter
        # but shorter than a normal fiscal year.
        if days < 120:
            continue

        if days > 340:
            continue

        candidates.append(
            (
                period,
                start,
                end,
                days,
            )
        )

    # --------------------------------------------------------
    # EXPECTED PRIOR TTM END
    #
    # The comparable TTM should normally end roughly one
    # fiscal year before current TTM.
    # --------------------------------------------------------

    prior_end_candidates = []

    for item in candidates:

        period, start, end, days = item

        gap = abs(
            (
                current_end_date
                - end
            ).days
            - 365
        )

        # Allow normal fiscal-year variation including
        # 52/53-week calendars.
        if gap <= 45:
            prior_end_candidates.append(
                (
                    gap,
                    -end.toordinal(),
                    item,
                )
            )

    prior_ytd = None

    if prior_end_candidates:

        prior_end_candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )

        prior_ytd = (
            prior_end_candidates[0][2][0]
        )

    # --------------------------------------------------------
    # FALLBACK:
    # derive prior YTD from current TTM start/end geometry.
    # --------------------------------------------------------

    if prior_ytd is None and current_start:

        current_start_date = _date(
            current_start
        )

        if current_start_date is not None:

            expected_end = (
                current_end_date
                - timedelta(days=365)
            )

            ranked = []

            for period, start, end, days in candidates:

                distance = abs(
                    (
                        end
                        - expected_end
                    ).days
                )

                if distance <= 60:
                    ranked.append(
                        (
                            distance,
                            -end.toordinal(),
                            period,
                        )
                    )

            if ranked:

                ranked.sort(
                    key=lambda item: (
                        item[0],
                        item[1],
                    )
                )

                prior_ytd = ranked[0][2]

    # --------------------------------------------------------
    # IF NO COMPARABLE YTD EXISTS:
    # fallback to a historical FY.
    #
    # This is intentionally last-resort behavior.
    # --------------------------------------------------------

    annual_candidates = []

    for period in all_periods:

        start = _date(
            _get(period, "start", None)
        )

        end = _date(
            _get(period, "end", None)
        )

        days = _duration(period)

        if (
            start is None
            or end is None
            or days is None
        ):
            continue

        if end >= current_end_date:
            continue

        if 350 <= days <= 380:

            distance = abs(
                (
                    current_end_date
                    - end
                ).days
                - 365
            )

            annual_candidates.append(
                (
                    distance,
                    -end.toordinal(),
                    period,
                )
            )

    # --------------------------------------------------------
    # FIND OLDER YTD
    #
    # Required for:
    #
    #   Prior FY
    #   - Older YTD
    #   + Prior YTD
    # --------------------------------------------------------

    older_ytd = None

    if prior_ytd is not None:

        prior_ytd_end = _date(
            getattr(
                prior_ytd,
                "end",
                None,
            )
        )

        prior_ytd_start = _date(
            getattr(
                prior_ytd,
                "start",
                None,
            )
        )

        if prior_ytd_end is not None:

            older_candidates = []

            for (
                period,
                start,
                end,
                days,
            ) in candidates:

                if end >= prior_ytd_end:
                    continue

                distance = abs(
                    (
                        prior_ytd_end
                        - end
                    ).days
                    - 365
                )

                if distance > 60:
                    continue

                # Prefer the same YTD start where possible.
                start_penalty = 0

                if (
                    prior_ytd_start is not None
                    and start != (
                        prior_ytd_start
                        - timedelta(days=365)
                    )
                ):
                    start_penalty = 1

                older_candidates.append(
                    (
                        distance,
                        start_penalty,
                        -end.toordinal(),
                        period,
                    )
                )

            if older_candidates:

                older_candidates.sort(
                    key=lambda item: (
                        item[0],
                        item[1],
                        item[2],
                    )
                )

                older_ytd = (
                    older_candidates[0][3]
                )

    # --------------------------------------------------------
    # FIND PRIOR FY
    #
    # Canonical bridge:
    #
    #   Prior FY
    #   - Older Comparable YTD
    #   + Prior Comparable YTD
    #   = Prior Comparable TTM
    #
    # IMPORTANT:
    # Prior FY must END BEFORE prior_ytd START.
    #
    # We must NOT select a FY that contains prior_ytd.
    # That would produce an invalid bridge such as:
    #
    #   FY2025 - YTD2024 + YTD2025
    #
    # which can create an impossible reconstructed period.
    # --------------------------------------------------------

    prior_fy = None

    if (
        prior_ytd is not None
        and older_ytd is not None
    ):

        older_ytd_start = _date(
            getattr(
                older_ytd,
                "start",
                None,
            )
        )

        older_ytd_end = _date(
            getattr(
                older_ytd,
                "end",
                None,
            )
        )

        prior_ytd_start = _date(
            getattr(
                prior_ytd,
                "start",
                None,
            )
        )

        if (
            older_ytd_start is not None
            and older_ytd_end is not None
            and prior_ytd_start is not None
        ):

            fy_candidates = []

            for period in all_periods:

                start = _date(
                    getattr(
                        period,
                        "start",
                        None,
                    )
                )

                end = _date(
                    getattr(
                        period,
                        "end",
                        None,
                    )
                )

                days = _duration(period)

                if (
                    start is None
                    or end is None
                    or days is None
                ):
                    continue

                if not (
                    350 <= days <= 380
                ):
                    continue

                # FY must contain the OLDER YTD.
                if start > older_ytd_start:
                    continue

                if end < older_ytd_end:
                    continue

                # CRITICAL:
                # FY must finish BEFORE the PRIOR YTD begins.
                if end >= prior_ytd_start:
                    continue

                start_distance = abs(
                    (
                        start
                        - older_ytd_start
                    ).days
                )

                end_distance = abs(
                    (
                        end
                        - older_ytd_end
                    ).days
                )

                fy_candidates.append(
                    (
                        start_distance,
                        end_distance,
                        -end.toordinal(),
                        period,
                    )
                )

            if fy_candidates:

                fy_candidates.sort(
                    key=lambda item: (
                        item[0],
                        item[1],
                        item[2],
                    )
                )

                prior_fy = (
                    fy_candidates[0][3]
                )

    # --------------------------------------------------------
    # RECONSTRUCT PRIOR TTM
    # --------------------------------------------------------

    if (
        prior_ytd is not None
        and older_ytd is not None
        and prior_fy is not None
    ):

        # The reconstructed TTM starts immediately after
        # the older comparable YTD ends.
        #
        # Do NOT use prior_fy.end here.
        # prior_fy.end is the end of the historical FY and
        # would incorrectly shift the reconstructed period
        # forward to the prior-YTD start.
        prior_start = (
            _date(
                getattr(
                    older_ytd,
                    "end",
                    None,
                )
            )
            + timedelta(days=1)
        )

        prior_end = _date(
            getattr(
                prior_ytd,
                "end",
                None,
            )
        )

        reconstructed = FinancialPeriod(
            period=(
                f"TTM:{prior_end.isoformat()}"
            ),
            start=prior_start.isoformat(),
            end=prior_end.isoformat(),
        )

        for field in flow_fields:

            fy_value = getattr(
                prior_fy,
                field,
                None,
            )

            old_ytd_value = getattr(
                older_ytd,
                field,
                None,
            )

            prior_ytd_value = getattr(
                prior_ytd,
                field,
                None,
            )

            if (
                fy_value is None
                or old_ytd_value is None
                or prior_ytd_value is None
            ):
                setattr(
                    reconstructed,
                    field,
                    None,
                )
                continue

            try:
                value = (
                    float(fy_value)
                    - float(old_ytd_value)
                    + float(prior_ytd_value)
                )

                # CapEx is canonicalized as positive.
                if field == "capex":
                    value = abs(value)

                setattr(
                    reconstructed,
                    field,
                    value,
                )

            except Exception:
                setattr(
                    reconstructed,
                    field,
                    None,
                )

        # Explicitly reconstruct FCF when OCF + CapEx exist.
        ocf = getattr(
            reconstructed,
            "operating_cash_flow",
            None,
        )

        capex = getattr(
            reconstructed,
            "capex",
            None,
        )

        if (
            ocf is not None
            and capex is not None
        ):
            reconstructed.free_cash_flow = (
                ocf - capex
            )

        return reconstructed

    # --------------------------------------------------------
    # LAST-RESORT FALLBACK
    #
    # Only use a raw FY if comparable TTM reconstruction is
    # impossible.
    # --------------------------------------------------------

    if annual_candidates:

        annual_candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )

        return annual_candidates[0][2]

    return None
def _atlas_apply_da_metrics(result):
    """
    Project canonical D&A and EBITDA metrics.

    EBITDA:
        operating_income + depreciation + amortization

    No value is fabricated when D&A is unavailable.
    """

    metrics = getattr(result, "metrics", None)

    if metrics is None:
        metrics = {}
        result.metrics = metrics

    ttm = getattr(result, "ttm", None)

    depreciation = getattr(
        ttm,
        "depreciation",
        None,
    )

    amortization = getattr(
        ttm,
        "amortization",
        None,
    )

    if depreciation is not None:
        metrics["depreciation"] = depreciation

    if amortization is not None:
        metrics["amortization"] = amortization

    if (
        depreciation is not None
        or amortization is not None
    ):
        depreciation_and_amortization = (
            (depreciation or 0.0)
            + (amortization or 0.0)
        )

        metrics[
            "depreciation_and_amortization"
        ] = depreciation_and_amortization

        operating_income = metrics.get(
            "operating_income"
        )

        if operating_income is not None:
            metrics["ebitda"] = (
                float(operating_income)
                + depreciation_and_amortization
            )

    return result


def _atlas_apply_canonical_metrics(result):
    """
    Project canonical financial metrics.

    Flow metrics:
        TRUE TTM

    Balance sheet:
        latest snapshot

    Growth:
        current TTM vs prior comparable TTM
    """

    ttm = getattr(result, "ttm", None)
    latest = getattr(result, "latest_period", None)
    periods = getattr(result, "periods", None) or []

    # --------------------------------------------------------
    # Existing metrics object
    # --------------------------------------------------------

    metrics = getattr(result, "metrics", None)

    if metrics is None:
        metrics = {}

        try:
            result.metrics = metrics
        except Exception:
            return result

    # --------------------------------------------------------
    # TRUE TTM FLOW METRICS
    # --------------------------------------------------------

    if ttm is not None:

        ttm_flow_fields = [
            "revenue",
            "gross_profit",
            "operating_income",
            "net_income",
            "operating_cash_flow",
            "capex",
            "free_cash_flow",
        ]

        for field in ttm_flow_fields:

            value = getattr(ttm, field, None)

            if value is not None:
                metrics[field] = value
            else:
                # Preserve explicit None rather than accidentally
                # falling back to latest quarter.
                metrics[field] = None

    # --------------------------------------------------------
    # BALANCE SHEET = LATEST SNAPSHOT
    # --------------------------------------------------------

    if latest is not None:

        balance_fields = [
            "assets",
            "equity",
            "cash",
            "debt",
        ]

        for field in balance_fields:

            value = getattr(latest, field, None)

            if value is not None:
                metrics[field] = value

    # --------------------------------------------------------
    # INTEREST EXPENSE
    #
    # Keep existing value if available.
    # Otherwise prefer TTM when available.
    # --------------------------------------------------------

    if ttm is not None:

        value = getattr(ttm, "interest_expense", None)

        if value is not None:
            metrics["interest_expense"] = value

    # --------------------------------------------------------
    # INCOME TAX EXPENSE
    #
    # Prefer TTM when the TTM period contains it.
    # Otherwise preserve existing normalized value.
    # --------------------------------------------------------

    if ttm is not None:

        value = getattr(ttm, "income_tax_expense", None)

        if value is not None:
            metrics["income_tax_expense"] = value

    # --------------------------------------------------------
    # TAX RATE
    #
    # Canonical:
    #
    #   income tax expense / pretax income
    #
    # If existing implementation already calculated a valid
    # value, preserve it unless we can derive a better TTM value.
    # --------------------------------------------------------

    tax_expense = metrics.get("income_tax_expense")

    pretax_income = None

    if ttm is not None:

        pretax_income = getattr(
            ttm,
            "pretax_income",
            None,
        )

        if pretax_income is None:

            # Some schemas expose income before taxes under
            # different names.
            for candidate in (
                "income_before_tax",
                "income_before_taxes",
                "pretax_income",
            ):
                value = getattr(ttm, candidate, None)

                if value is not None:
                    pretax_income = value
                    break

    if (
        tax_expense is not None
        and pretax_income is not None
        and pretax_income != 0
    ):
        metrics["tax_rate"] = (
            abs(float(tax_expense))
            / abs(float(pretax_income))
        )

    # --------------------------------------------------------
    # PRIOR COMPARABLE TTM
    # --------------------------------------------------------

    prior_ttm = _atlas_find_prior_ttm(
        periods,
        ttm,
    )

    # --------------------------------------------------------
    # GROWTH = TTM VS PRIOR TTM
    # --------------------------------------------------------

    if (
        ttm is not None
        and prior_ttm is not None
    ):

        current_revenue = getattr(
            ttm,
            "revenue",
            None,
        )

        prior_revenue = getattr(
            prior_ttm,
            "revenue",
            None,
        )

        if (
            current_revenue is not None
            and prior_revenue is not None
            and prior_revenue != 0
        ):
            metrics["revenue_growth"] = (
                float(current_revenue)
                / float(prior_revenue)
                - 1.0
            )

        current_net_income = getattr(
            ttm,
            "net_income",
            None,
        )

        prior_net_income = getattr(
            prior_ttm,
            "net_income",
            None,
        )

        if (
            current_net_income is not None
            and prior_net_income is not None
            and prior_net_income != 0
        ):
            metrics["net_income_growth"] = (
                float(current_net_income)
                / float(prior_net_income)
                - 1.0
            )

        current_fcf = getattr(
            ttm,
            "free_cash_flow",
            None,
        )

        prior_fcf = getattr(
            prior_ttm,
            "free_cash_flow",
            None,
        )

        if (
            current_fcf is not None
            and prior_fcf is not None
            and prior_fcf != 0
        ):
            metrics["fcf_growth"] = (
                float(current_fcf)
                / float(prior_fcf)
                - 1.0
            )
        else:
            metrics["fcf_growth"] = None

        # Optional audit metadata.
        try:
            if isinstance(getattr(result, "evidence", None), dict):
                result.evidence[
                    "canonical_metric_source"
                ] = {
                    "flow_metrics": "true_ttm",
                    "balance_sheet": "latest_period",
                    "growth": "ttm_vs_prior_ttm",
                    "ttm_end": getattr(ttm, "end", None),
                    "prior_ttm_end": getattr(
                        prior_ttm,
                        "end",
                        None,
                    ),
                }
        except Exception:
            pass

    else:

        # No comparable prior TTM.
        # Do NOT calculate misleading latest/prior growth.
        metrics["revenue_growth"] = None
        metrics["net_income_growth"] = None
        metrics["fcf_growth"] = None

    return result


# ============================================================
# INSTALL WRAPPER ON FinancialFactNormalizer
# ============================================================

_original_normalize = FinancialFactNormalizer._normalize_raw


def _atlas_normalize_canonical(self, *args, **kwargs):
    result = _original_normalize(
        self,
        *args,
        **kwargs,
    )

    # --------------------------------------------------------
    # CANONICAL METRICS
    # --------------------------------------------------------

    result = _atlas_apply_canonical_metrics(
        result
    )

    # --------------------------------------------------------
    # D&A / EBITDA METRICS
    #
    # _atlas_apply_da_metrics already contains the canonical
    # propagation logic. The previous bug was that this function
    # existed but was never activated by the live normalize path.
    # --------------------------------------------------------

    result = _atlas_apply_da_metrics(
        result
    )

    return result


FinancialFactNormalizer.normalize = _atlas_normalize_canonical


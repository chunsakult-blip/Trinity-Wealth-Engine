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

from datetime import date, timedelta
from typing import Any

from .models import FinancialPeriod, NormalizedFinancials


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
            "LongTermDebtNoncurrent",
            "LongTermDebtCurrent",
            "LongTermDebt",
            "ShortTermBorrowings",
            "DebtCurrent",
            "Borrowings",
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
                and 250 <= days(period) <= 300
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
                    # Assemble quarterly TTM only if derived Q4 exists.
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

    def normalize(
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
        # GROWTH
        # --------------------------------------------------------------

        metrics["revenue_growth"] = None
        metrics["net_income_growth"] = None
        metrics["fcf_growth"] = None

        if (
            latest_period
            and prior_period
        ):

            if (
                latest_period.revenue is not None
                and prior_period.revenue
                not in (
                    None,
                    0,
                )
            ):

                metrics["revenue_growth"] = (
                    latest_period.revenue
                    / prior_period.revenue
                    - 1.0
                )

            if (
                latest_period.net_income is not None
                and prior_period.net_income
                not in (
                    None,
                    0,
                )
            ):

                metrics["net_income_growth"] = (
                    latest_period.net_income
                    / prior_period.net_income
                    - 1.0
                )

            if (
                latest_period.free_cash_flow is not None
                and prior_period.free_cash_flow
                not in (
                    None,
                    0,
                )
            ):

                metrics["fcf_growth"] = (
                    latest_period.free_cash_flow
                    / prior_period.free_cash_flow
                    - 1.0
                )

        # --------------------------------------------------------------
        # TRUE TTM
        # --------------------------------------------------------------

        true_ttm = self._build_true_ttm(
            periods
        )

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


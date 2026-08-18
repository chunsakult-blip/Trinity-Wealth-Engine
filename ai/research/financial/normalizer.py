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

from datetime import date
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

        if not periods:
            return None

        def days(period: FinancialPeriod) -> int | None:

            if not period.start or not period.end:
                return None

            try:
                return (
                    date.fromisoformat(period.end)
                    - date.fromisoformat(period.start)
                ).days

            except (TypeError, ValueError):
                return None

        duration = [
            period
            for period in periods
            if days(period) is not None
        ]

        # ==============================================================
        # SEC YTD -> TRUE TTM
        # ==============================================================

        ytd = [
            period
            for period in duration
            if (
                days(period) is not None
                and 250 <= days(period) <= 300
            )
        ]

        if ytd:

            current = max(
                ytd,
                key=lambda item: item.end or "",
            )

            if not current.end:
                return None

            try:
                prev_year = str(
                    int(current.end[:4]) - 1
                )
            except ValueError:
                return None

            # Same month/day YTD from prior year.
            pytd = [
                period
                for period in duration
                if (
                    period.end
                    and period.end[:4] == prev_year
                    and period.end[4:] == current.end[4:]
                    and days(period) is not None
                    and 250 <= days(period) <= 300
                )
            ]

            # Prior-year full year.
            pfy = [
                period
                for period in duration
                if (
                    period.end
                    and period.end[:4] == prev_year
                    and days(period) is not None
                    and days(period) >= 300
                )
            ]

            if pytd and pfy:

                previous_ytd = max(
                    pytd,
                    key=lambda item: item.end or "",
                )

                previous_fy = max(
                    pfy,
                    key=lambda item: item.end or "",
                )

                def calc(
                    name: str,
                ) -> float | None:

                    current_value = getattr(
                        current,
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

                revenue = calc("revenue")

                # Revenue remains mandatory.
                if revenue is not None:

                    ocf = calc(
                        "operating_cash_flow"
                    )

                    capex = calc(
                        "capex"
                    )

                    free_cash_flow = None

                    if (
                        ocf is not None
                        and capex is not None
                    ):
                        free_cash_flow = (
                            ocf - abs(capex)
                        )

                    return FinancialPeriod(

                        period=(
                            f"TTM:{current.end}"
                        ),

                        start=current.start,
                        end=current.end,

                        revenue=revenue,

                        gross_profit=calc(
                            "gross_profit"
                        ),

                        operating_income=calc(
                            "operating_income"
                        ),

                        net_income=calc(
                            "net_income"
                        ),

                        assets=current.assets,
                        equity=current.equity,
                        cash=current.cash,
                        debt=current.debt,

                        operating_cash_flow=ocf,

                        capex=(
                            abs(capex)
                            if capex is not None
                            else None
                        ),

                        free_cash_flow=free_cash_flow,

                        interest_expense=calc(
                            "interest_expense"
                        ),
                    )

        # ==============================================================
        # Quarterly TTM
        # ==============================================================

        quarters = [
            period
            for period in duration
            if (
                days(period) is not None
                and 70 <= days(period) <= 110
            )
        ]

        if len(quarters) >= 4:

            qs = sorted(
                quarters,
                key=lambda item: item.end or "",
                reverse=True,
            )[:4]

            latest = qs[0]

            operating_cash_flow = sum(
                (
                    item.operating_cash_flow
                    for item in qs
                    if item.operating_cash_flow is not None
                ),
                0.0,
            )

            capex_values = [
                item.capex
                for item in qs
                if item.capex is not None
            ]

            # IMPORTANT:
            #
            # Do NOT turn missing CapEx into zero.
            #
            # If even one quarter is missing CapEx, the
            # quarterly TTM FCF is considered unavailable.
            capex = None

            if len(capex_values) == len(qs):
                capex = sum(
                    abs(value)
                    for value in capex_values
                )

            ocf_values = [
                item.operating_cash_flow
                for item in qs
                if item.operating_cash_flow is not None
            ]

            operating_cash_flow_value = None

            if len(ocf_values) == len(qs):
                operating_cash_flow_value = sum(
                    ocf_values
                )

            free_cash_flow = None

            if (
                operating_cash_flow_value is not None
                and capex is not None
            ):
                free_cash_flow = (
                    operating_cash_flow_value
                    - capex
                )

            return FinancialPeriod(

                period=f"TTM:{latest.end}",

                start=qs[-1].start,
                end=latest.end,

                revenue=sum(
                    (
                        item.revenue
                        for item in qs
                        if item.revenue is not None
                    ),
                    0.0,
                ),

                gross_profit=(
                    sum(
                        (
                            item.gross_profit
                            for item in qs
                            if item.gross_profit is not None
                        ),
                        0.0,
                    )
                    if all(
                        item.gross_profit is not None
                        for item in qs
                    )
                    else None
                ),

                operating_income=(
                    sum(
                        (
                            item.operating_income
                            for item in qs
                            if item.operating_income is not None
                        ),
                        0.0,
                    )
                    if all(
                        item.operating_income is not None
                        for item in qs
                    )
                    else None
                ),

                net_income=(
                    sum(
                        (
                            item.net_income
                            for item in qs
                            if item.net_income is not None
                        ),
                        0.0,
                    )
                    if all(
                        item.net_income is not None
                        for item in qs
                    )
                    else None
                ),

                assets=latest.assets,
                equity=latest.equity,
                cash=latest.cash,
                debt=latest.debt,

                operating_cash_flow=(
                    operating_cash_flow_value
                ),

                capex=capex,

                free_cash_flow=free_cash_flow,

                interest_expense=(
                    sum(
                        (
                            item.interest_expense
                            for item in qs
                            if item.interest_expense is not None
                        ),
                        0.0,
                    )
                    if all(
                        item.interest_expense is not None
                        for item in qs
                    )
                    else None
                ),
            )

        # ==============================================================
        # Annual fallback
        #
        # IMPORTANT:
        # If YTD data exists but cannot construct a true TTM,
        # do NOT fabricate a TTM from an annual period.
        # ==============================================================

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


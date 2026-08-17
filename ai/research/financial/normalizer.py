"""
Provider-neutral financial fact normalizer.

Responsibilities:
- extract SEC XBRL concepts
- select deterministic facts
- construct canonical financial periods
- normalize CapEx sign convention
- calculate only period-level FCF
- expose normalized raw metrics

Derived analytical ratios belong to metrics.py.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .models import FinancialPeriod, NormalizedFinancials


class FinancialFactNormalizer:

    CONCEPTS = {
        "revenue": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
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
        ),
        "net_income": (
            "NetIncomeLoss",
            "ProfitLoss",
        ),
        "assets": (
            "Assets",
        ),
        "equity": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "PartnersCapital",
            "MemberEquity",
        ),
        "cash": (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
        "debt": (
            "LongTermDebtNoncurrent",
            "LongTermDebtCurrent",
            "LongTermDebt",
            "ShortTermBorrowings",
            "DebtCurrent",
        ),
        "operating_cash_flow": (
            "NetCashProvidedByUsedInOperatingActivities",
        ),
        "capex": (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
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





    def _build_true_ttm(
        self,
        periods: list[FinancialPeriod],
    ) -> FinancialPeriod | None:


        if not periods:
            return None


        def days(p):

            if not p.start or not p.end:
                return None

            try:
                return (
                    date.fromisoformat(p.end)
                    -
                    date.fromisoformat(p.start)
                ).days
            except:
                return None


        duration=[
            p for p in periods
            if days(p) is not None
        ]


        # =========================
        # SEC YTD TTM
        # =========================

        ytd=[
            p for p in duration
            if 250 <= days(p) <= 300
        ]


        if ytd:

            current=max(
                ytd,
                key=lambda x:x.end or ""
            )

            prev_year=str(
                int(current.end[:4])-1
            )


            pytd=[
                p for p in duration
                if (
                    p.end
                    and p.end[:4]==prev_year
                    and p.end[4:]==current.end[4:]
                    and 250 <= days(p) <= 300
                )
            ]


            pfy=[
                p for p in duration
                if (
                    p.end
                    and p.end[:4]==prev_year
                    and days(p)>=300
                )
            ]


            if pytd and pfy:

                pytd=max(pytd,key=lambda x:x.end)
                pfy=max(pfy,key=lambda x:x.end)


                def calc(name):

                    c=getattr(current,name,None)
                    p=getattr(pytd,name,None)
                    f=getattr(pfy,name,None)

                    if c is None:
                        return None

                    if p is None or f is None:
                        return None

                    return f-p+c


                revenue=calc("revenue")


                # revenue is mandatory
                if revenue is not None:

                    ocf=calc(
                        "operating_cash_flow"
                    )

                    capex=calc(
                        "capex"
                    )


                    return FinancialPeriod(

                        period=f"TTM:{current.end}",

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


                        capex=abs(capex)
                        if capex is not None
                        else None,


                        free_cash_flow=(
                            ocf-abs(capex)
                            if ocf is not None
                            and capex is not None
                            else None
                        ),


                        interest_expense=calc(
                            "interest_expense"
                        ),

                    )


        # =========================
        # Quarterly TTM
        # =========================

        quarters=[
            p for p in duration
            if 70 <= days(p)<=110
        ]


        if len(quarters)>=4:

            qs=sorted(
                quarters,
                key=lambda x:x.end or "",
                reverse=True
            )[:4]


            a=qs[0]


            return FinancialPeriod(

                period=f"TTM:{a.end}",

                start=qs[-1].start,

                end=a.end,


                revenue=sum(
                    x.revenue or 0
                    for x in qs
                ),

                gross_profit=sum(
                    x.gross_profit or 0
                    for x in qs
                ),


                operating_income=sum(
                    x.operating_income or 0
                    for x in qs
                ),


                net_income=sum(
                    x.net_income or 0
                    for x in qs
                ),


                assets=a.assets,
                equity=a.equity,
                cash=a.cash,
                debt=a.debt,


                operating_cash_flow=sum(
                    x.operating_cash_flow or 0
                    for x in qs
                ),


                capex=sum(
                    x.capex or 0
                    for x in qs
                ),


                free_cash_flow=sum(
                    x.free_cash_flow or 0
                    for x in qs
                ),

                interest_expense=sum(
                    x.interest_expense or 0
                    for x in qs
                ),
            )


        # =========================
        # Annual fallback
        # =========================
        #
        # IMPORTANT:
        # If SEC YTD exists but failed completeness check,
        # never fallback to annual.
        # Otherwise we fabricate TTM.
        #

        if ytd:
            return None


        annual=[
            p for p in duration
            if days(p)>=300
        ]


        if annual:

            p=max(
                annual,
                key=lambda x:x.end or ""
            )


            return FinancialPeriod(

                period=f"TTM:{p.end}",

                start=p.start,

                end=p.end,


                revenue=p.revenue,

                gross_profit=p.gross_profit,

                operating_income=p.operating_income,

                net_income=p.net_income,


                assets=p.assets,

                equity=p.equity,

                cash=p.cash,

                debt=p.debt,


                operating_cash_flow=p.operating_cash_flow,

                capex=p.capex,

                free_cash_flow=p.free_cash_flow,

                interest_expense=p.interest_expense,
            )


        return None



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

        facts_root = payload.get("facts", {})

        if not isinstance(facts_root, dict):
            raise ValueError(
                "SEC Company Facts payload missing facts."
            )

        us_gaap = facts_root.get("us-gaap", {})

        if not isinstance(us_gaap, dict):
            raise ValueError(
                "SEC Company Facts payload missing us-gaap."
            )

        concept_values: dict[
            str,
            list[dict[str, Any]]
        ] = {}

        evidence: list[dict[str, Any]] = []

        # ------------------------------------------------------------
        # EXTRACT
        # ------------------------------------------------------------

        for metric_name, concepts in self.CONCEPTS.items():

            values: list[dict[str, Any]] = []

            for concept in concepts:

                node = us_gaap.get(concept)

                if not isinstance(node, dict):
                    continue

                units = node.get("units", {})

                if not isinstance(units, dict):
                    continue

                for unit, entries in units.items():

                    if not isinstance(entries, list):
                        continue

                    for entry in entries:

                        if not isinstance(entry, dict):
                            continue

                        value = entry.get("val")
                        end = entry.get("end")

                        if value is None or end is None:
                            continue

                        item = dict(entry)

                        item["_concept"] = concept
                        item["_unit"] = unit

                        values.append(item)

            concept_values[metric_name] = values

            if values:
                evidence.append(
                    {
                        "type": "sec_xbrl",
                        "metric": metric_name,
                        "concepts": sorted(
                            {
                                item["_concept"]
                                for item in values
                            }
                        ),
                        "count": len(values),
                    }
                )

        # ------------------------------------------------------------
        # SELECT DETERMINISTIC FACT
        # ------------------------------------------------------------

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
                    float
                ]
            ] = []

            for item in values:

                value = item.get("val")
                end = item.get("end")

                if value is None or end is None:
                    continue

                if end_date is not None and end != end_date:
                    continue

                if start_date is not None:
                    if item.get("start") != start_date:
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
                    item.get("form", "")
                ).upper()

                fp = str(
                    item.get("fp", "")
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

                ten_k_preference = (
                    1
                    if form == "10-K"
                    else 0
                )

                filed = str(
                    item.get("filed", "")
                )

                # Deterministic preference:
                # newest end -> annual duration -> FY -> 10-K -> filed
                score = (
                    end,
                    annual_preference,
                    fy_preference,
                    ten_k_preference,
                    filed,
                )

                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
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

        # ------------------------------------------------------------
        # DISCOVER PERIOD KEYS
        # ------------------------------------------------------------

        period_keys: set[
            tuple[str | None, str | None]
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

        # ------------------------------------------------------------
        # DEDUPLICATE INSTANT VS DURATION PERIODS
        #
        # SEC Company Facts can contain both:
        #
        #     start=2025-01-01, end=2025-12-31
        #
        # and:
        #
        #     start=None, end=2025-12-31
        #
        # The latter is an instant fact (normally balance-sheet data).
        # It must not become a second FinancialPeriod when a real
        # duration period with the same end date already exists.
        #
        # Therefore:
        #
        #   duration exists for end -> remove instant duplicate
        #   duration does not exist -> retain instant period
        # ------------------------------------------------------------

        duration_ends = {
            end
            for start, end in period_keys
            if start is not None and end is not None
        }

        deduplicated_keys = {
            (start, end)
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

        # ------------------------------------------------------------
        # BUILD PERIODS
        # ------------------------------------------------------------

        periods: list[FinancialPeriod] = []

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

            # CapEx canonical convention:
            # always positive cash outflow.
            if period.capex is not None:
                period.capex = abs(
                    period.capex
                )

            if (
                period.revenue is not None
                or period.net_income is not None
                or period.assets is not None
                or period.equity is not None
                or period.operating_cash_flow is not None
            ):

                if (
                    period.operating_cash_flow is not None
                    and period.capex is not None
                ):
                    period.free_cash_flow = (
                        period.operating_cash_flow
                        - period.capex
                    )

                periods.append(period)

        # ------------------------------------------------------------
        # LATEST / PRIOR
        # ------------------------------------------------------------

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

        # ------------------------------------------------------------
        # PROVIDER-NEUTRAL BASE METRICS
        # ------------------------------------------------------------

        metrics: dict[
            str,
            float | None
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
                    if latest_period
                    and metric_name in self.DURATION_METRICS
                    else None
                ),
            )

        # Canonical FCF in metrics.
        if latest_period is not None:
            metrics["free_cash_flow"] = (
                latest_period.free_cash_flow
            )
        else:
            metrics["free_cash_flow"] = None

        # ------------------------------------------------------------
        # TAX RATE
        # ------------------------------------------------------------

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
                net_income + income_tax
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

        # ------------------------------------------------------------
        # GROWTH
        # ------------------------------------------------------------

        metrics["revenue_growth"] = None
        metrics["net_income_growth"] = None
        metrics["fcf_growth"] = None

        if latest_period and prior_period:

            if (
                latest_period.revenue is not None
                and prior_period.revenue not in (
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
                and prior_period.net_income not in (
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
                and prior_period.free_cash_flow not in (
                    None,
                    0,
                )
            ):
                metrics["fcf_growth"] = (
                    latest_period.free_cash_flow
                    / prior_period.free_cash_flow
                    - 1.0
                )

        true_ttm = self._build_true_ttm(
            periods
        )

        return NormalizedFinancials(
            cik=cik,
            ticker=ticker,
            company_name=entity_name,
            currency="USD",
            latest_period=latest_period,
            prior_period=prior_period,
            ttm=true_ttm,
            periods=periods,
            metrics=metrics,
            quality={},
            evidence=evidence,
        )


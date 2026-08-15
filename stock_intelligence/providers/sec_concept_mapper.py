from __future__ import annotations

from typing import Any, Mapping, Optional


# ----------------------------------------------------------------------
# Canonical SEC concept priorities.
#
# Earlier concepts have higher priority.
# The mapper is deliberately deterministic.
# ----------------------------------------------------------------------

CONCEPT_MAP: dict[str, tuple[str, ...]] = {
    "revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
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
    "ocf": (
        "NetCashProvidedByUsedInOperatingActivities",
    ),
    "capex": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ),
    "cash": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "debt": (
        "LongTermDebtNoncurrent",
        "LongTermDebtCurrent",
        "LongTermDebt",
    ),
    "assets": (
        "Assets",
    ),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "PartnersCapital",
    ),
    "shares": (
        "EntityCommonStockSharesOutstanding",
    ),
}


class SECConceptMapper:
    """
    Offline mapper for SEC Company Facts structures.

    Responsibilities:
        SEC concept names
            ->
        canonical financial fields

    This class performs NO network activity.
    """

    def __init__(
        self,
        concept_map: Optional[
            Mapping[str, tuple[str, ...]]
        ] = None,
    ) -> None:

        self.concept_map = dict(
            concept_map or CONCEPT_MAP
        )

        self._reverse_map: dict[str, str] = {}

        for canonical_field, concepts in self.concept_map.items():

            for concept in concepts:

                # First registered canonical field wins.
                if concept not in self._reverse_map:
                    self._reverse_map[concept] = (
                        canonical_field
                    )

    def canonical_field(
        self,
        concept: str,
    ) -> Optional[str]:

        return self._reverse_map.get(concept)

    def known_concept(
        self,
        concept: str,
    ) -> bool:

        return concept in self._reverse_map

    def known_fields(self) -> tuple[str, ...]:

        return tuple(
            self.concept_map.keys()
        )

    def map_concepts(
        self,
        facts: Mapping[str, Any],
    ) -> dict[str, Any]:

        mapped: dict[str, Any] = {}

        for concept, value in facts.items():

            canonical = self.canonical_field(
                concept
            )

            if canonical is None:
                continue

            # Deterministic first-value-wins behavior.
            if canonical not in mapped:
                mapped[canonical] = value

        return mapped

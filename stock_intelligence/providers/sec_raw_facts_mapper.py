from __future__ import annotations

from typing import Any, Mapping, Optional

from .sec_concept_mapper import (
    SECConceptMapper,
)
from .sec_period_resolver import (
    SECPeriodResolver,
)
from .sec_unit_resolver import (
    SECUnitResolver,
)


class SECRawFactsMapper:
    """
    Converts an offline SEC Company Facts-like payload
    into canonical raw financial records.

    This class does NOT normalize financial ratios.

    It only resolves:

        SEC concept
        SEC unit
        SEC observation
        fiscal period
        provenance metadata

    into canonical raw financial fields.
    """

    def __init__(
        self,
        concept_mapper: Optional[
            SECConceptMapper
        ] = None,
    ) -> None:

        self.concept_mapper = (
            concept_mapper
            or SECConceptMapper()
        )

    @staticmethod
    def _concept_name(
        key: str,
    ) -> str:

        if ":" in key:
            return key.split(
                ":",
                1,
            )[1]

        return key

    @staticmethod
    def _is_supported_unit(
        observation: Mapping[str, Any],
    ) -> bool:

        return SECUnitResolver.supported(
            observation
        )

    def map_payload(
        self,
        ticker: str,
        payload: Mapping[str, Any],
    ) -> list[dict[str, Any]]:

        facts = payload.get(
            "facts",
            {},
        )

        us_gaap = facts.get(
            "us-gaap",
            {},
        )

        records: dict[
            str,
            dict[str, Any]
        ] = {}

        for raw_key, concept_data in us_gaap.items():

            concept = self._concept_name(
                str(raw_key)
            )

            canonical = (
                self.concept_mapper.canonical_field(
                    concept
                )
            )

            if canonical is None:
                continue

            units = concept_data.get(
                "units",
                {},
            )

            for unit_name, observations in units.items():

                if unit_name not in (
                    "USD",
                    "shares",
                    "USD/shares",
                ):
                    continue

                if not isinstance(
                    observations,
                    list,
                ):
                    continue

                for observation in observations:

                    if not isinstance(
                        observation,
                        Mapping,
                    ):
                        continue

                    if not self._is_supported_unit(
                        {
                            **observation,
                            "unit": unit_name,
                        }
                    ):
                        continue

                    value = SECUnitResolver.normalize_value(
                        {
                            **observation,
                            "unit": unit_name,
                        }
                    )

                    if value is None:
                        continue

                    fiscal_period = (
                        SECPeriodResolver.fiscal_period(
                            observation
                        )
                    )

                    if fiscal_period is None:
                        continue

                    record = records.setdefault(
                        fiscal_period,
                        {
                            "fiscal_period":
                                fiscal_period,
                            "_provenance": [],
                        },
                    )

                    # --------------------------------------------------
                    # Deterministic conflict rule:
                    #
                    # For the same canonical field + period,
                    # retain the observation with the latest filing date.
                    # --------------------------------------------------

                    existing = record.get(
                        canonical
                    )

                    candidate_filed = str(
                        observation.get(
                            "filed",
                            "",
                        )
                    )

                    replace = False

                    if existing is None:

                        replace = True

                    else:

                        existing_filed = str(
                            existing.get(
                                "_filed",
                                "",
                            )
                        )

                        replace = (
                            candidate_filed
                            > existing_filed
                        )

                    if replace:

                        record[canonical] = {
                            "value": value,
                            "_filed":
                                candidate_filed,
                            "_form":
                                observation.get(
                                    "form"
                                ),
                            "_accn":
                                observation.get(
                                    "accn"
                                ),
                            "_frame":
                                observation.get(
                                    "frame"
                                ),
                            "_start":
                                observation.get(
                                    "start"
                                ),
                            "_end":
                                observation.get(
                                    "end"
                                ),
                            "_unit":
                                unit_name,
                        }

        output: list[dict[str, Any]] = []

        for fiscal_period in sorted(
            records.keys()
        ):

            source_record = records[
                fiscal_period
            ]

            canonical_record: dict[
                str,
                Any
            ] = {
                "fiscal_period":
                    fiscal_period
            }

            provenance = []

            for field_name, value_record in (
                source_record.items()
            ):

                if field_name in (
                    "fiscal_period",
                    "_provenance",
                ):
                    continue

                if not isinstance(
                    value_record,
                    Mapping,
                ):
                    continue

                canonical_record[
                    field_name
                ] = value_record[
                    "value"
                ]

                provenance.append(
                    {
                        "field":
                            field_name,
                        "source":
                            "SEC",
                        "accession":
                            value_record.get(
                                "_accn"
                            ),
                        "form":
                            value_record.get(
                                "_form"
                            ),
                        "filed":
                            value_record.get(
                                "_filed"
                            ),
                        "unit":
                            value_record.get(
                                "_unit"
                            ),
                        "start":
                            value_record.get(
                                "_start"
                            ),
                        "end":
                            value_record.get(
                                "_end"
                            ),
                    }
                )

            canonical_record[
                "_provenance"
            ] = provenance

            canonical_record[
                "_ticker"
            ] = ticker

            output.append(
                canonical_record
            )

        return output

# ============================================================================
# NICK V3 — 04D.1 COMPATIBILITY API
# ============================================================================
#
# Purpose:
#   Preserve the existing SECRawFactsMapper class while exposing a stable
#   functional API for downstream pipeline stages such as 04F.
#
# This layer intentionally does NOT:
#   - perform network calls
#   - modify SEC payloads
#   - ingest securities
#   - bypass the canonical mapper
#
# ============================================================================


def map_company_facts(
    company_facts,
    ticker: str = "",
    fiscal_period: Optional[str] = None,
):
    """
    Stable functional entry point for SEC Company Facts mapping.

    Delegates to the canonical SECRawFactsMapper implementation.

    The wrapper intentionally performs API compatibility only.
    """

    mapper = SECRawFactsMapper()

    # Try the canonical mapper API without assuming its exact historical
    # method name. This keeps 04D compatible with 04F while preserving
    # the existing implementation.
    candidate_methods = [
        "map",
        "map_facts",
        "map_company_facts",
        "transform",
        "process",
        "run",
    ]

    for method_name in candidate_methods:

        method = getattr(
            mapper,
            method_name,
            None,
        )

        if callable(method):

            try:
                return method(
                    company_facts,
                    ticker=ticker,
                    fiscal_period=fiscal_period,
                )
            except TypeError:

                try:
                    return method(
                        company_facts,
                        ticker=ticker,
                    )
                except TypeError:

                    try:
                        return method(
                            company_facts,
                        )
                    except TypeError:
                        continue

    raise AttributeError(
        "SECRawFactsMapper does not expose a supported "
        "mapping method. Expected one of: "
        + ", ".join(candidate_methods)
    )

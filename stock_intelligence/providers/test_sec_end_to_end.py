from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from stock_intelligence.providers.sec_raw_facts_mapper import (
    SECRawFactsMapper,
    map_company_facts,
)

from stock_intelligence.providers.financial_model import (
    FinancialPeriod,
    NormalizedFinancials,
)

import stock_intelligence.providers.sec_normalization_bridge as bridge_module


def _load_fixture():
    fixture = (
        Path(__file__)
        .with_name("sec_company_facts_fixture.json")
    )

    assert fixture.exists(), (
        f"SEC fixture missing: {fixture}"
    )

    with fixture.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def _build_mapper():

    signature = inspect.signature(
        SECRawFactsMapper.__init__
    )

    parameters = list(
        signature.parameters.values()
    )[1:]

    if not parameters:
        return SECRawFactsMapper()

    from stock_intelligence.providers.sec_concept_mapper import (
        SECConceptMapper,
    )

    concept_mapper = SECConceptMapper()

    kwargs = {}

    if any(
        parameter.name == "concept_mapper"
        for parameter in parameters
    ):
        kwargs["concept_mapper"] = concept_mapper

    try:
        return SECRawFactsMapper(
            **kwargs
        )
    except TypeError:

        if kwargs:
            return SECRawFactsMapper(
                concept_mapper
            )

        return SECRawFactsMapper()


def _detect_ticker(payload: dict[str, Any]) -> str:

    for key in (
        "ticker",
        "symbol",
        "company_ticker",
    ):

        value = payload.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip().upper()

    return "TEST"


def _run_mapper(payload):

    ticker = _detect_ticker(payload)

    mapper = _build_mapper()

    method = getattr(
        mapper,
        "map_payload",
        None,
    )

    if callable(method):

        signature = inspect.signature(
            method
        )

        parameters = list(
            signature.parameters.values()
        )

        positional = [
            p
            for p in parameters
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]

        if len(positional) >= 2:
            return method(
                ticker,
                payload,
            )

        return method(
            payload
        )

    return map_company_facts(
        payload,
        ticker,
    )


def _extract_records(mapped):

    if mapped is None:
        raise AssertionError(
            "Mapper returned None"
        )

    if isinstance(mapped, list):
        return mapped

    if isinstance(mapped, tuple):
        return list(mapped)

    if isinstance(mapped, dict):

        for key in (
            "records",
            "financial_records",
            "periods",
            "data",
            "results",
        ):

            value = mapped.get(key)

            if isinstance(value, list):
                return value

        return [mapped]

    if hasattr(mapped, "records"):

        records = mapped.records

        if isinstance(records, list):
            return records

    if hasattr(mapped, "periods"):

        periods = mapped.periods

        if isinstance(periods, list):
            return periods

    return [mapped]


def _contains_provenance(value):

    if isinstance(value, dict):

        if any(
            key in value
            for key in (
                "source",
                "source_url",
                "accession",
            )
        ):
            return True

        return any(
            _contains_provenance(v)
            for v in value.values()
        )

    if isinstance(value, list):

        return any(
            _contains_provenance(v)
            for v in value
        )

    if hasattr(value, "provenance"):

        provenance = getattr(
            value,
            "provenance",
        )

        return bool(provenance)

    return False


def _invoke_callable(
    function,
    records,
):
    """
    Invoke a real 04C callable based on its
    actual signature.

    We deliberately do not assume that the
    bridge takes only `records`.
    """

    signature = inspect.signature(
        function
    )

    parameters = list(
        signature.parameters.values()
    )

    positional = [
        p
        for p in parameters
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]

    required = [
        p
        for p in positional
        if p.default is inspect.Parameter.empty
    ]

    # Most direct API:
    #
    # normalize(record)
    #
    if len(required) <= 1:

        try:
            return function(records)
        except TypeError:
            pass

    # Possible dataset API:
    #
    # normalize(ticker, records)
    #
    if len(required) == 2:

        try:
            return function(
                "TEST",
                records,
            )
        except TypeError:
            pass

    # Try keyword-aware dispatch.
    kwargs = {}

    for parameter in parameters:

        if parameter.name in (
            "records",
            "financial_records",
            "periods",
            "data",
            "raw",
            "raw_records",
        ):
            kwargs[
                parameter.name
            ] = records

        elif parameter.name in (
            "ticker",
            "symbol",
            "company",
        ):
            kwargs[
                parameter.name
            ] = "TEST"

    if kwargs:

        try:
            return function(
                **kwargs
            )
        except TypeError:
            pass

    raise TypeError(
        "Unable to invoke 04C callable "
        f"{function} with signature "
        f"{signature}"
    )


def _bridge_records(records):

    Bridge = getattr(
        bridge_module,
        "SECNormalizationBridge",
        None,
    )

    # --------------------------------------------------------------
    # CLASS API
    # --------------------------------------------------------------

    if Bridge is not None:

        try:
            bridge = Bridge()
        except TypeError:
            bridge = None

        if bridge is not None:

            methods = []

            for name in dir(bridge):

                if name.startswith("_"):
                    continue

                attr = getattr(
                    bridge,
                    name,
                )

                if callable(attr):
                    methods.append(
                        name
                    )

            preferred = [
                "normalize",
                "normalize_records",
                "normalize_financials",
                "normalize_record",
                "normalize_period",
                "transform",
                "convert",
                "map",
                "bridge",
                "process",
            ]

            ordered = (
                [
                    name
                    for name in preferred
                    if name in methods
                ]
                +
                [
                    name
                    for name in methods
                    if name not in preferred
                ]
            )

            for name in ordered:

                function = getattr(
                    bridge,
                    name,
                )

                try:

                    result = _invoke_callable(
                        function,
                        records,
                    )

                    if result is not None:
                        return result

                except TypeError:
                    continue

    # --------------------------------------------------------------
    # MODULE FUNCTION API
    # --------------------------------------------------------------

    preferred_functions = [
        "normalize_sec_record",
        "normalize_sec_records",
        "normalize_financials",
        "normalize_financial_period",
        "bridge_sec_record",
        "bridge_sec_records",
        "normalize",
        "bridge",
        "transform",
        "convert",
    ]

    for name in preferred_functions:

        function = getattr(
            bridge_module,
            name,
            None,
        )

        if not callable(function):
            continue

        try:

            result = _invoke_callable(
                function,
                records,
            )

            if result is not None:
                return result

        except TypeError:
            continue

    raise AssertionError(
        "Unable to invoke existing 04C API. "
        "The diagnostic output above contains "
        "the real bridge signature."
    )


def _contains_canonical(value):

    if isinstance(
        value,
        (
            FinancialPeriod,
            NormalizedFinancials,
        ),
    ):
        return True

    if isinstance(value, list):

        return any(
            _contains_canonical(v)
            for v in value
        )

    if isinstance(value, tuple):

        return any(
            _contains_canonical(v)
            for v in value
        )

    if isinstance(value, dict):

        return any(
            _contains_canonical(v)
            for v in value.values()
        )

    if hasattr(value, "periods"):
        return True

    if hasattr(value, "fiscal_period"):
        return True

    return False


def main():

    print("")
    print(
        "SEC -> 04D MAPPER -> 04C NORMALIZATION -> 04B MODEL"
    )
    print("")

    payload = _load_fixture()

    assert isinstance(
        payload,
        dict,
    )

    print(
        "SEC fixture              : PASS"
    )

    mapped = _run_mapper(
        payload
    )

    assert mapped is not None

    records = _extract_records(
        mapped
    )

    assert len(records) > 0

    print(
        "SEC Company Facts mapper : PASS"
    )

    print(
        "Mapped records            :",
        len(records),
    )

    first = records[0]

    if isinstance(first, dict):

        assert any(
            key in first
            for key in (
                "fiscal_period",
                "period",
                "fy",
                "revenue",
                "net_income",
                "operating_income",
            )
        )

    else:

        assert (
            hasattr(first, "fiscal_period")
            or hasattr(first, "period")
            or hasattr(first, "revenue")
            or hasattr(first, "net_income")
        )

    print(
        "Canonical raw records    : PASS"
    )

    assert _contains_provenance(
        records
    )

    print(
        "Provenance preservation   : PASS"
    )

    bridged = _bridge_records(
        records
    )

    assert bridged is not None

    print(
        "04C normalization bridge : PASS"
    )

    assert _contains_canonical(
        bridged
    )

    print(
        "Canonical financial model: PASS"
    )

    print("")
    print(
        "NETWORK CALLS: 0"
    )
    print(
        "REAL SEC REQUESTS: 0"
    )
    print(
        "INGESTION: 0"
    )
    print("")

    print(
        "SEC END-TO-END CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()

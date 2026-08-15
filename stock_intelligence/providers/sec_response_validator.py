from __future__ import annotations

from typing import Any, Mapping


class SECResponseValidationError(ValueError):
    """Raised when a SEC API response is structurally invalid."""


def validate_json_object(
    payload: Any,
    *,
    endpoint: str = "",
) -> Mapping[str, Any]:

    if not isinstance(payload, Mapping):
        raise SECResponseValidationError(
            f"SEC response must be a JSON object"
            + (
                f" for endpoint={endpoint}"
                if endpoint
                else ""
            )
        )

    return payload


def validate_company_facts_response(
    payload: Any,
) -> Mapping[str, Any]:

    data = validate_json_object(
        payload,
        endpoint="companyfacts",
    )

    required = [
        "entityName",
        "facts",
    ]

    missing = [
        key
        for key in required
        if key not in data
    ]

    if missing:
        raise SECResponseValidationError(
            "SEC Company Facts response missing "
            f"required fields: {missing}"
        )

    if not isinstance(
        data["facts"],
        Mapping,
    ):
        raise SECResponseValidationError(
            "SEC Company Facts 'facts' must be an object"
        )

    return data


def validate_submissions_response(
    payload: Any,
) -> Mapping[str, Any]:

    data = validate_json_object(
        payload,
        endpoint="submissions",
    )

    required = [
        "name",
        "cik",
    ]

    missing = [
        key
        for key in required
        if key not in data
    ]

    if missing:
        raise SECResponseValidationError(
            "SEC submissions response missing "
            f"required fields: {missing}"
        )

    return data

from datetime import date
from math import ceil
from typing import Any

from app.schemas.validation import (
    ValidationCheck,
    ValidationRequest,
    ValidationResponse,
    ValidationStatus,
)


def _get_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def _collect_values(value: Any, accepted_keys: set[str]) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in accepted_keys and isinstance(child, (str, int, float)):
                found.append(child)
            found.extend(_collect_values(child, accepted_keys))
    elif isinstance(value, list):
        for child in value:
            found.extend(_collect_values(child, accepted_keys))
    return found


def _add_check(
    checks: list[ValidationCheck],
    field: str,
    status: ValidationStatus,
    message: str,
    evidence: list[str] | None = None,
) -> None:
    checks.append(ValidationCheck(field=field, status=status, message=message, evidence=evidence or []))


def validate_travel_data(request: ValidationRequest) -> ValidationResponse:
    data = request.data
    checks: list[ValidationCheck] = []
    missing: list[str] = []
    as_of = request.as_of or date.today()

    for field_name in request.required_fields:
        value = _get_path(data, field_name)
        if value is None or value == "":
            missing.append(field_name)
            _add_check(checks, field_name, ValidationStatus.MISSING, "Required information was not provided.")
        else:
            _add_check(checks, field_name, ValidationStatus.PASS, "Required information is present.")

    adults = data.get("adults")
    children = data.get("children")
    total = data.get("total_travelers", data.get("totalTravelers"))
    if adults is not None and children is not None:
        if adults < 0 or children < 0:
            _add_check(checks, "travelers", ValidationStatus.FAIL, "Adult and child counts cannot be negative.")
        elif total is not None and total != adults + children:
            _add_check(
                checks,
                "total_travelers",
                ValidationStatus.FAIL,
                "Total travelers do not equal adults plus children.",
                [f"adults={adults}", f"children={children}", f"total={total}"],
            )
        else:
            _add_check(checks, "travelers", ValidationStatus.PASS, "Traveler counts are internally consistent.")

    start_value = data.get("start_date", data.get("startDate"))
    end_value = data.get("end_date", data.get("endDate"))
    if start_value and end_value:
        try:
            start_date = date.fromisoformat(str(start_value))
            end_date = date.fromisoformat(str(end_value))
        except ValueError:
            _add_check(checks, "travel_dates", ValidationStatus.FAIL, "Travel dates must use ISO YYYY-MM-DD format.")
        else:
            if end_date < start_date:
                _add_check(checks, "travel_dates", ValidationStatus.FAIL, "End date is before start date.", [str(start_value), str(end_value)])
            else:
                _add_check(checks, "travel_dates", ValidationStatus.PASS, "Travel dates are ordered correctly.")

    occupancy = data.get("room_occupancy", data.get("roomOccupancy"))
    required_rooms = data.get("required_rooms", data.get("requiredRooms"))
    if adults is not None and children is not None and occupancy:
        minimum_rooms = ceil((adults + children) / occupancy)
        if required_rooms is not None and required_rooms < minimum_rooms:
            _add_check(
                checks,
                "required_rooms",
                ValidationStatus.FAIL,
                "Room count does not meet the supplied occupancy requirement.",
                [f"required_rooms={required_rooms}", f"minimum_rooms={minimum_rooms}", f"occupancy={occupancy}"],
            )
        elif required_rooms is not None:
            _add_check(checks, "required_rooms", ValidationStatus.PASS, "Room count meets the supplied occupancy requirement.")

    documents = data.get("documents", [])
    for index, document in enumerate(documents if isinstance(documents, list) else []):
        expires = document.get("expires_on", document.get("expiry_date")) if isinstance(document, dict) else None
        if not expires:
            continue
        try:
            expiry_date = date.fromisoformat(str(expires))
        except ValueError:
            _add_check(checks, f"documents[{index}].expires_on", ValidationStatus.NEEDS_REVIEW, "Expiry date cannot be parsed.", [str(expires)])
        else:
            status = ValidationStatus.FAIL if expiry_date < as_of else ValidationStatus.PASS
            message = "Document is expired." if status is ValidationStatus.FAIL else "Document has not expired as of the validation date."
            _add_check(checks, f"documents[{index}].expires_on", status, message, [f"expires_on={expiry_date.isoformat()}", f"as_of={as_of.isoformat()}"])

    conflicts = False
    comparable_fields = {
        "start_date": {"start_date", "startDate"},
        "end_date": {"end_date", "endDate"},
        "destination": {"destination", "to_destination", "toDestination"},
        "booking_reference": {"booking_reference", "bookingReference", "pnr"},
    }
    for canonical_name, keys in comparable_fields.items():
        values: list[str] = []
        for agent_name, output in request.agent_outputs.items():
            values.extend(f"{agent_name}:{item}" for item in _collect_values(output, keys))
        distinct = {entry.split(":", 1)[1].strip().casefold() for entry in values}
        if len(distinct) > 1:
            conflicts = True
            _add_check(
                checks,
                canonical_name,
                ValidationStatus.FAIL,
                "Agent outputs contain conflicting values.",
                values,
            )

    for agent_name, output in request.agent_outputs.items():
        if not isinstance(output, dict):
            _add_check(checks, f"agent_outputs.{agent_name}", ValidationStatus.NEEDS_REVIEW, "Agent output is not an object and cannot be reconciled.")
            continue
        output_status = str(output.get("status", "")).casefold()
        data_status = str(output.get("data_status", "")).casefold()
        if output_status in {"not_configured", "partial", "needs_information", "conditional", "needs_review"} or data_status in {"not_configured", "unknown", "unverified"}:
            _add_check(
                checks,
                f"agent_outputs.{agent_name}",
                ValidationStatus.NEEDS_REVIEW,
                "Agent result is partial, unverified or dependent on an unavailable provider.",
                [f"status={output.get('status', 'not supplied')}", f"data_status={output.get('data_status', 'not supplied')}"],
            )

    known_rules = {
        "trip_integrity",
        "cross_agent_consistency",
        "document_expiry",
        "output_schema",
        "airport_proximity",
        "cancellation_policy",
        "room_occupancy",
        "finance_balance",
        "meal_code",
    }
    for rule in request.applicable_rules:
        if rule not in known_rules:
            _add_check(
                checks,
                f"applicable_rules.{rule}",
                ValidationStatus.NEEDS_REVIEW,
                "No deterministic validator is available for this named rule.",
            )

    if not request.applicable_rules and not request.required_fields:
        _add_check(
            checks,
            "applicable_rules",
            ValidationStatus.NEEDS_REVIEW,
            "No validation rules were supplied; compliance cannot be determined.",
        )

    statuses = {check.status for check in checks}
    if ValidationStatus.FAIL in statuses:
        overall = ValidationStatus.FAIL
    elif ValidationStatus.MISSING in statuses:
        overall = ValidationStatus.MISSING
    elif ValidationStatus.NEEDS_REVIEW in statuses:
        overall = ValidationStatus.NEEDS_REVIEW
    elif ValidationStatus.WARNING in statuses:
        overall = ValidationStatus.WARNING
    else:
        overall = ValidationStatus.PASS

    return ValidationResponse(
        status=overall,
        checks=checks,
        missing_information=missing,
        has_conflicts=conflicts,
    )
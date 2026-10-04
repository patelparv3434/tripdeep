from datetime import date

from app.schemas.validation import ValidationRequest, ValidationStatus
from app.validators.travel import validate_travel_data


def test_valid_trip_inputs_pass() -> None:
    result = validate_travel_data(
        ValidationRequest(
            data={
                "origin": "Ahmedabad",
                "destination": "Munnar",
                "start_date": "2026-11-08",
                "end_date": "2026-11-15",
                "adults": 12,
                "children": 2,
                "total_travelers": 14,
                "room_occupancy": 2,
                "required_rooms": 7,
            },
            required_fields=["origin", "destination", "start_date", "end_date"],
            applicable_rules=["trip_integrity"],
        )
    )

    assert result.status is ValidationStatus.PASS
    assert not result.missing_information


def test_missing_required_field_returns_missing() -> None:
    result = validate_travel_data(
        ValidationRequest(data={"origin": "Ahmedabad"}, required_fields=["destination"])
    )

    assert result.status is ValidationStatus.MISSING
    assert result.missing_information == ["destination"]


def test_conflicting_dates_across_agents_fail() -> None:
    result = validate_travel_data(
        ValidationRequest(
            data={"start_date": "2026-11-08", "end_date": "2026-11-15"},
            agent_outputs={
                "itinerary": {"start_date": "2026-11-08"},
                "booking": {"startDate": "2026-11-09"},
            },
            applicable_rules=["cross_agent_consistency"],
        )
    )

    assert result.status is ValidationStatus.FAIL
    assert result.has_conflicts


def test_expired_document_fails_against_explicit_date() -> None:
    result = validate_travel_data(
        ValidationRequest(
            data={"documents": [{"document_type": "passport", "expires_on": "2025-12-31"}]},
            applicable_rules=["document_expiry"],
            as_of=date(2026, 10, 2),
        )
    )

    assert result.status is ValidationStatus.FAIL


def test_missing_rules_do_not_return_pass() -> None:
    result = validate_travel_data(ValidationRequest(data={"destination": "Munnar"}))

    assert result.status is ValidationStatus.NEEDS_REVIEW
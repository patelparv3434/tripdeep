def test_agent_catalog_is_dynamic_and_includes_validator(client) -> None:
    response = client.get("/api/agents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 12
    assert {agent["id"] for agent in payload["agents"]} >= {"validator", "dietitian", "weather"}


def test_validator_execution_persists_result(client) -> None:
    response = client.post(
        "/api/agents/validator/execute",
        json={
            "input_data": {
                "data": {"destination": "Munnar"},
                "required_fields": ["destination"],
                "applicable_rules": ["trip_integrity"],
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["validation_status"] == "PASS"
    result = client.get(f"/api/validation/{payload['execution_id']}")
    assert result.status_code == 200
    assert result.json()["status"] == "PASS"


def test_agent_exception_creates_visible_reproduction_case(client) -> None:
    response = client.post(
        "/api/agents/validator/execute",
        json={"input_data": {"data": "malformed"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    case_id = payload["reproduction_case_id"]
    error = client.get(f"/api/errors/{case_id}")
    assert error.status_code == 200
    assert error.json()["error_type"] == "ValidationError"
    assert client.get("/api/errors").json()["total"] == 1


def test_reproduction_case_can_be_replayed(client) -> None:
    failed = client.post(
        "/api/agents/validator/execute",
        json={"input_data": {"data": "malformed"}},
    ).json()

    replay = client.post(f"/api/reproduction/{failed['reproduction_case_id']}/replay")

    assert replay.status_code == 200
    assert replay.json()["status"] == "reproduced"
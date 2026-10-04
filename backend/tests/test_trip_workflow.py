from datetime import date, timedelta
from unittest.mock import AsyncMock


def test_create_trip_calculates_rooms_and_traveler_total(client) -> None:
    response = client.post(
        "/api/trips",
        json={
            "origin": "Ahmedabad",
            "destination": "Munnar",
            "start_date": "2026-11-08",
            "end_date": "2026-11-15",
            "adults": 12,
            "children": 2,
            "travel_mode": "Flight",
            "room_occupancy": 2,
        },
    )

    assert response.status_code == 201, response.text
    trip = response.json()
    assert trip["request_data"]["total_travelers"] == 14
    assert trip["request_data"]["required_rooms"] == 7


def test_trip_workflow_runs_selected_agent_then_validator(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.trips.resolve_destination",
        AsyncMock(
            return_value=(
                {
                    "name": "Munnar",
                    "country": "India",
                    "latitude": 10.08,
                    "longitude": 77.06,
                    "timezone": "Asia/Kolkata",
                },
                None,
            )
        ),
    )
    trip = client.post(
        "/api/trips",
        json={
            "origin": "Ahmedabad",
            "destination": "Munnar",
            "start_date": "2026-11-08",
            "end_date": "2026-11-15",
            "adults": 12,
            "children": 2,
            "travel_mode": "Flight",
        },
    ).json()

    response = client.post(
        f"/api/trips/{trip['id']}/plan",
        json={"agents": [{"agent_id": "weather", "input_data": {}}]},
    )

    assert response.status_code == 200, response.text
    workflow = response.json()
    assert len(workflow["executions"]) == 1
    assert workflow["final_validation"]["agent_id"] == "validator"
    assert workflow["final_validation"]["validation_status"] == "NEEDS_REVIEW"
    assert workflow["status"] == "needs_review"


def test_trip_plan_runs_orchestration_and_returns_customer_sections(client, monkeypatch, tmp_path) -> None:
    today = date.today()
    start_date = today + timedelta(days=2)
    end_date = start_date + timedelta(days=2)
    monkeypatch.setattr(
        "app.api.trips.resolve_destination",
        AsyncMock(
            return_value=(
                {
                    "name": "Munnar",
                    "country": "India",
                    "latitude": 10.08,
                    "longitude": 77.06,
                    "timezone": "Asia/Kolkata",
                },
                None,
            )
        ),
    )
    monkeypatch.setattr(
        "app.agents.weather_agent.get_destination_weather",
        AsyncMock(
            return_value=(
                {
                    "daily": {
                        "time": [start_date.isoformat()],
                        "weather_code": [1],
                        "temperature_2m_max": [25.0],
                        "temperature_2m_min": [15.0],
                        "precipitation_probability_max": [10],
                        "wind_speed_10m_max": [12.0],
                    }
                },
                None,
            )
        ),
    )
    hotels = [
        {
            "name": "Verified-tag hotel",
            "type": "hotel",
            "star_rating": "4",
            "source": "https://www.openstreetmap.org/node/1",
            "retrieved_at": "2026-10-04T00:00:00+00:00",
        },
        {
            "name": "Unrated map listing",
            "type": "guest_house",
            "star_rating": None,
            "source": "https://www.openstreetmap.org/node/3",
            "retrieved_at": "2026-10-04T00:00:00+00:00",
        },
    ]
    monkeypatch.setattr(
        "app.agents.hotel_agent.find_nearby_places",
        AsyncMock(return_value=(hotels, None)),
    )
    attractions = [
        {
            "name": "Munnar Museum",
            "type": "museum",
            "source": "https://www.openstreetmap.org/node/2",
        }
    ]
    monkeypatch.setattr(
        "app.agents.tour_guide_agent.find_nearby_places",
        AsyncMock(return_value=(attractions, None)),
    )

    trip = client.post(
        "/api/trips",
        json={
            "origin": "Ahmedabad",
            "destination": "Munnar",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "adults": 2,
            "children": 0,
            "hotel_category": "Hotel / Guest house",
            "travel_mode": "Flight",
        },
    ).json()

    from app.api import documents

    monkeypatch.setattr(documents.settings, "upload_directory", str(tmp_path))
    uploaded_document = client.post(
        f"/api/documents?trip_id={trip['id']}",
        files={
            "file": (
                "travel_insurance_policy.txt",
                b"Example policy text; verify all terms with the insurer.",
                "text/plain",
            )
        },
    )
    assert uploaded_document.status_code == 201, uploaded_document.text

    response = client.post(f"/api/trips/{trip['id']}/plan")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["plan"]["title"] == "Your trip to Munnar"
    sections = {section["id"]: section for section in payload["plan"]["sections"]}
    assert sections["weather"]["items"][0]["condition"] == "Mainly clear"
    assert sections["hotels"]["items"] == hotels
    assert sections["activities"]["items"] == attractions
    assert len(sections["itinerary"]["items"]) == 3
    assert sections["itinerary"]["items"][0]["activities"][0]["name"] == "Munnar Museum"
    assert sections["clothing"]["items"][0]["activities"] == ["Munnar Museum"]
    assert sections["documents"]["details"]["attached_documents"][0]["original_name"] == "travel_insurance_policy.txt"
    insurance_check = next(
        item for item in sections["documents"]["items"]
        if item["category"] == "Travel insurance policy"
    )
    assert insurance_check["status"] == "candidate_attached"
    assert sections["insurance"]["items"][0]["name"] == "travel_insurance_policy.txt"
    assert "coverage and exclusions still need review" in sections["insurance"]["summary"]
    assert sections["budget"]["status"] == "partial"
    assert "No verified provider prices" in sections["budget"]["summary"]
    assert "validator" not in response.text

    executions = client.get(f"/api/trips/{trip['id']}/executions").json()["executions"]
    execution_agents = {execution["agent_id"] for execution in executions}
    assert {
        "travel_planner",
        "weather",
        "hotel",
        "tour_guide",
        "document",
        "insurance",
        "finance",
        "validator",
    } <= execution_agents

    saved_plan = client.get(f"/api/trips/{trip['id']}/plan")
    assert saved_plan.status_code == 200
    assert saved_plan.json()["plan"] == payload["plan"]
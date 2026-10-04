from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.api import dependencies
from app.core.config import Settings


class MockAuthResponse:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.status_code = 200

    def json(self) -> dict[str, str]:
        return {"id": self.user_id, "email": f"{self.user_id}@example.test"}

    def raise_for_status(self) -> None:
        return None


class MockAuthClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def get(self, url: str, headers: dict[str, str]) -> MockAuthResponse:
        assert url == "https://auth.example.test/auth/v1/user"
        assert headers["apikey"] == "public-test-key"
        token = headers["Authorization"].removeprefix("Bearer ")
        return MockAuthResponse(token)


def test_production_login_requires_supabase_identity_and_scopes_trips(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    from app.api import documents

    settings = Settings(
        environment="production",
        supabase_url="https://auth.example.test",
        supabase_anon_key="public-test-key",
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    monkeypatch.setattr(dependencies.httpx, "AsyncClient", MockAuthClient)
    monkeypatch.setattr(documents.settings, "upload_directory", str(tmp_path))

    today = date.today() + timedelta(days=10)
    request = {
        "origin": "Ahmedabad",
        "destination": "Munnar",
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=2)).isoformat(),
        "adults": 1,
        "children": 0,
    }

    unauthenticated = client.get("/api/trips")
    assert unauthenticated.status_code == 401

    created = client.post(
        "/api/trips",
        json=request,
        headers={"Authorization": "Bearer user-a"},
    )
    assert created.status_code == 201, created.text
    trip_id = created.json()["id"]

    other_user_trips = client.get(
        "/api/trips",
        headers={"Authorization": "Bearer user-b"},
    )
    other_user_trip = client.get(
        f"/api/trips/{trip_id}",
        headers={"Authorization": "Bearer user-b"},
    )
    assert other_user_trips.status_code == 200
    assert other_user_trips.json()["trips"] == []
    assert other_user_trip.status_code == 404

    uploaded = client.post(
        "/api/documents",
        files={"file": ("policy.txt", b"Private policy text", "text/plain")},
        headers={"Authorization": "Bearer user-a"},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    other_user_documents = client.get(
        "/api/documents",
        headers={"Authorization": "Bearer user-b"},
    )
    other_user_document = client.get(
        f"/api/documents/{document_id}",
        headers={"Authorization": "Bearer user-b"},
    )
    assert other_user_documents.status_code == 200
    assert other_user_documents.json()["documents"] == []
    assert other_user_document.status_code == 404

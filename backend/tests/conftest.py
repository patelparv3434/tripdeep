import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_db
from app.db.memory import MemoryDatabase
from app.main import app as fastapi_app


@pytest.fixture
def client():
    database = MemoryDatabase()

    async def override_database():
        yield database

    fastapi_app.dependency_overrides[get_db] = override_database
    test_client = TestClient(fastapi_app)
    yield test_client
    test_client.close()
    fastapi_app.dependency_overrides.clear()
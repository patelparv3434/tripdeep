from math import ceil
from datetime import datetime, timezone
from uuid import uuid4

from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings
from app.schemas.trips import TripCreateRequest


async def local_user(database: AsyncDatabase) -> dict:
    if get_settings().environment != "development":
        raise RuntimeError("Authentication provider is not configured")
    user_id = "local-dev-owner"
    await database.users.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"email": "local@tripdeep.dev", "role": "owner", "status": "active", "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return await database.users.find_one({"_id": user_id})


async def create_trip(
    database: AsyncDatabase,
    payload: TripCreateRequest,
    request_id: str,
    user: dict,
) -> dict:
    trip_id = str(uuid4())
    now = datetime.now(timezone.utc)
    request_data = payload.model_dump(mode="json")
    request_data["total_travelers"] = payload.adults + payload.children
    request_data["required_rooms"] = ceil((payload.adults + payload.children) / payload.room_occupancy)
    trip = {
        "_id": trip_id,
        "user_id": user["_id"],
        "title": payload.title or f"{payload.origin} to {payload.destination}",
        "origin": payload.origin,
        "destination": payload.destination,
        "start_date": payload.start_date.isoformat(),
        "end_date": payload.end_date.isoformat(),
        "status": "draft",
        "request_data": request_data,
        "created_at": now,
        "updated_at": now,
    }
    await database.trips.insert_one(trip)
    await database.audit_logs.insert_one({
        "_id": str(uuid4()),
        "request_id": request_id,
        "user_id": user["_id"],
        "trip_id": trip_id,
        "action": "trip_created",
        "entity_type": "trip",
        "entity_id": trip_id,
        "details": {"status": "draft"},
        "created_at": now,
    })
    return trip
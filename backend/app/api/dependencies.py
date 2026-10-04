from collections.abc import AsyncIterator

import httpx
from fastapi import Depends, Header, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings
from app.db.session import database
from app.db.memory import MemoryDatabase
from app.services.trip_service import local_user


async def get_db() -> AsyncIterator[AsyncDatabase | MemoryDatabase]:
    yield database


async def get_current_user(
    authorization: str | None = Header(default=None),
    database: AsyncDatabase | MemoryDatabase = Depends(get_db),
) -> dict:
    settings = get_settings()
    if settings.environment == "development":
        return await local_user(database)
    if settings.environment != "production":
        raise HTTPException(status_code=503, detail="Authentication is not configured for this environment")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in to access this resource")
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=503, detail="Authentication provider is not configured")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to access this resource")
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_anon_key,
                    "Authorization": f"Bearer {token}",
                },
            )
        if response.status_code in {401, 403}:
            raise HTTPException(status_code=401, detail="Your session is invalid or expired")
        response.raise_for_status()
        identity = response.json()
        if not isinstance(identity, dict):
            raise HTTPException(
                status_code=401,
                detail="Authentication provider returned an invalid identity",
            )
        user_id = identity.get("id")
        if not isinstance(user_id, str) or not user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication provider returned an invalid identity",
            )
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Authentication provider could not be reached",
        ) from error

    user = {
        "_id": user_id,
        "email": identity.get("email"),
        "role": "user",
        "status": "active",
    }
    await database.users.update_one(
        {"_id": user_id},
        {"$set": user},
        upsert=True,
    )
    return user
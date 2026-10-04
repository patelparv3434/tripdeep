from urllib.parse import quote

import httpx

from app.core.config import get_settings


def _storage_url(object_key: str) -> tuple[str, str]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Persistent document storage is not configured")
    path = quote(object_key, safe="/")
    return (
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/"
        f"{quote(settings.supabase_storage_bucket, safe='')}/{path}",
        settings.supabase_service_role_key,
    )


async def store_document(object_key: str, content: bytes, media_type: str) -> None:
    url, service_key = _storage_url(object_key)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                content=content,
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": media_type,
                    "x-upsert": "false",
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise RuntimeError(
            "Persistent document upload request failed"
        ) from error


async def read_document(object_key: str) -> bytes:
    url, service_key = _storage_url(object_key)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise RuntimeError(
            "Persistent document download request failed"
        ) from error
    return response.content

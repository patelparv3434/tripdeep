import csv
import hashlib
import io
import json
import mimetypes
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.api.dependencies import get_current_user, get_db
from app.core.config import get_settings
from app.integrations.supabase_storage import read_document, store_document

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()
ALLOWED_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".txt": {"text/plain"},
    ".csv": {"text/csv", "application/vnd.ms-excel", "application/octet-stream"},
    ".json": {"application/json", "text/json", "text/plain"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
}


def safe_extract(extension: str, content: bytes) -> tuple[str, dict | None]:
    if extension == ".txt":
        return "extracted", {"text": content.decode("utf-8", errors="replace")}
    if extension == ".json":
        try:
            return "extracted", {"data": json.loads(content)}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "needs_review", None
    if extension == ".csv":
        text = content.decode("utf-8", errors="replace")
        return "extracted", {"rows": list(csv.DictReader(io.StringIO(text)))}
    return "extraction_not_configured", None


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    trip_id: str | None = None,
    database: AsyncDatabase = Depends(get_db),
    owner: dict = Depends(get_current_user),
) -> dict[str, object]:
    original_name = Path(file.filename or "upload").name
    extension = Path(original_name).suffix.lower()
    expected_types = ALLOWED_TYPES.get(extension)
    media_type = file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    if expected_types is None or media_type not in expected_types:
        raise HTTPException(status_code=415, detail="Unsupported document type")

    content = await file.read(settings.upload_max_bytes + 1)
    if len(content) > settings.upload_max_bytes:
        raise HTTPException(status_code=413, detail="Document exceeds the configured upload limit")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded document is empty")
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="File content does not match PDF type")
    if extension == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="File content does not match PNG type")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="File content does not match JPEG type")

    if trip_id and await database.trips.find_one({"_id": trip_id, "user_id": owner["_id"]}) is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    document_id = str(uuid4())
    storage_name = (
        f"{owner['_id']}/{document_id}{extension}"
        if settings.environment == "production"
        else f"{document_id}{extension}"
    )
    if settings.environment == "production":
        try:
            await store_document(storage_name, content, media_type)
        except RuntimeError as error:
            raise HTTPException(
                status_code=502,
                detail="The document could not be saved to persistent storage",
            ) from error
    else:
        storage_root = Path(settings.upload_directory).resolve()
        storage_path = (storage_root / storage_name).resolve()
        if storage_root not in storage_path.parents:
            raise HTTPException(status_code=400, detail="Invalid storage path")
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(content)
    extraction_status, extracted_data = safe_extract(extension, content)
    now = datetime.now(timezone.utc)
    document = {
        "_id": document_id,
        "user_id": owner["_id"],
        "trip_id": trip_id,
        "original_name": original_name[:255],
        "storage_key": storage_name,
        "media_type": media_type,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "document_type": None,
        "status": extraction_status,
        "extracted_data": extracted_data,
        "created_at": now,
        "updated_at": now,
    }
    await database.documents.insert_one(document)
    return {
        "id": document_id,
        "original_name": document["original_name"],
        "media_type": media_type,
        "size_bytes": len(content),
        "status": extraction_status,
        "extracted_data": extracted_data,
        "validation_status": "NEEDS_REVIEW",
        "message": "Extracted values are unverified; compare them with the source document.",
    }


@router.get("")
async def list_documents(
    database: AsyncDatabase = Depends(get_db),
    owner: dict = Depends(get_current_user),
) -> dict[str, object]:
    documents = await database.documents.find({"user_id": owner["_id"]}).sort("created_at", DESCENDING).to_list(length=500)
    return {"documents": [{"id": item["_id"], "trip_id": item.get("trip_id"), "original_name": item["original_name"], "media_type": item["media_type"], "size_bytes": item["size_bytes"], "status": item["status"], "created_at": item.get("created_at")} for item in documents], "total": len(documents)}


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    database: AsyncDatabase = Depends(get_db),
    owner: dict = Depends(get_current_user),
) -> dict[str, object]:
    document = await database.documents.find_one({"_id": document_id, "user_id": owner["_id"]})
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"id": document["_id"], "trip_id": document.get("trip_id"), "original_name": document["original_name"], "media_type": document["media_type"], "size_bytes": document["size_bytes"], "status": document["status"], "extracted_data": document.get("extracted_data"), "sha256": document["sha256"], "validation_status": "NEEDS_REVIEW"}


@router.get("/{document_id}/file")
async def download_document(
    document_id: str,
    database: AsyncDatabase = Depends(get_db),
    owner: dict = Depends(get_current_user),
) -> Response:
    document = await database.documents.find_one(
        {"_id": document_id, "user_id": owner["_id"]}
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if settings.environment == "production":
        try:
            content = await read_document(document["storage_key"])
        except RuntimeError as error:
            raise HTTPException(
                status_code=502,
                detail="The document could not be retrieved from persistent storage",
            ) from error
    else:
        storage_root = Path(settings.upload_directory).resolve()
        storage_path = (storage_root / document["storage_key"]).resolve()
        if storage_root not in storage_path.parents or not storage_path.is_file():
            raise HTTPException(status_code=404, detail="Document file not found")
        content = storage_path.read_bytes()
    return Response(
        content=content,
        media_type=document["media_type"],
        headers={
            "Content-Disposition": (
                "attachment; filename*=UTF-8''"
                + quote(document["original_name"], safe="")
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
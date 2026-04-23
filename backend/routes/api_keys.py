"""
API Key management routes
"""
import secrets
import hashlib
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Request, HTTPException
from backend.models import APIKeyCreate, APIKeyResponse, APIKeyListResponse
from backend.middleware import validate_admin_token, hash_api_key
from backend.database import db
from backend.config import settings

router = APIRouter(prefix="/admin/api-keys")


def generate_api_key() -> str:
    random_part = secrets.token_hex(settings.API_KEY_LENGTH // 2)
    return f"{settings.API_KEY_PREFIX}{random_part}"


@router.post("", response_model=APIKeyResponse)
async def create_api_key(request: Request, body: APIKeyCreate):
    await validate_admin_token(request)

    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)

    doc = {
        "name": body.name,
        "key_hash": key_hash,
        "key_preview": f"{raw_key[:8]}...{raw_key[-4:]}",
        "description": body.description or "",
        "rate_limit": body.rate_limit or settings.RATE_LIMIT_PER_MINUTE,
        "is_active": True,
        "total_requests": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used": None,
    }

    result = await db.api_keys().insert_one(doc)

    return APIKeyResponse(
        id=str(result.inserted_id),
        name=body.name,
        key=raw_key,
        key_preview=doc["key_preview"],
        created_at=doc["created_at"],
        is_active=True,
        rate_limit=doc["rate_limit"],
        description=doc["description"],
    )


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(request: Request):
    await validate_admin_token(request)

    cursor = db.api_keys().find().sort("created_at", -1)
    keys = []
    async for doc in cursor:
        keys.append(APIKeyResponse(
            id=str(doc["_id"]),
            name=doc["name"],
            key_preview=doc["key_preview"],
            created_at=doc["created_at"],
            last_used=doc.get("last_used"),
            is_active=doc.get("is_active", True),
            rate_limit=doc.get("rate_limit", 30),
            total_requests=doc.get("total_requests", 0),
            description=doc.get("description", ""),
        ))

    return APIKeyListResponse(keys=keys, total=len(keys))


@router.delete("/{key_id}")
async def revoke_api_key(request: Request, key_id: str):
    await validate_admin_token(request)

    result = await db.api_keys().update_one(
        {"_id": ObjectId(key_id)},
        {"$set": {"is_active": False}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail={"error": {"message": "Key not found"}})

    return {"message": "API key revoked"}

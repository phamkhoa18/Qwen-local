"""
Admin routes - login, stats, RAG management, health checks
"""
import jwt
import time
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from backend.models import AdminLoginRequest, AdminLoginResponse
from backend.middleware import validate_admin_token
from backend.database import db
from backend.config import settings
from backend.services.ollama_service import ollama_service
from backend.services.rag_service import rag_service
from backend.services.vector_store import vector_store

router = APIRouter(prefix="/admin")

_start_time = time.time()


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(body: AdminLoginRequest):
    if body.username != settings.ADMIN_USERNAME or body.password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail={"error": {"message": "Invalid credentials"}})

    token = jwt.encode(
        {"role": "admin", "sub": body.username, "exp": datetime.now(timezone.utc) + timedelta(days=1)},
        settings.SECRET_KEY, algorithm="HS256"
    )
    return AdminLoginResponse(access_token=token)


@router.get("/health")
async def health_check():
    ollama_ok = await ollama_service.is_available()
    mongo_ok = await db.is_connected()

    return {
        "status": "ok" if (ollama_ok and mongo_ok) else "degraded",
        "version": settings.APP_VERSION,
        "ollama_connected": ollama_ok,
        "mongodb_connected": mongo_ok,
        "rag_ready": rag_service.is_ready,
        "default_model": settings.DEFAULT_MODEL,
        "total_legal_chunks": vector_store.total_chunks,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "indexing": rag_service._indexing,
        "indexing_progress": rag_service.index_progress,
    }


@router.get("/usage")
async def usage_stats(request: Request):
    await validate_admin_token(request)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    pipeline_total = [{"$group": {
        "_id": None,
        "total_requests": {"$sum": 1},
        "total_tokens": {"$sum": "$total_tokens"},
        "total_prompt": {"$sum": "$prompt_tokens"},
        "total_completion": {"$sum": "$completion_tokens"},
        "avg_response": {"$avg": "$response_time_ms"},
    }}]

    pipeline_today = [
        {"$match": {"timestamp": {"$gte": today_start.isoformat()}}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "tokens": {"$sum": "$total_tokens"}}}
    ]

    pipeline_daily = [
        {"$addFields": {"date": {"$substr": ["$timestamp", 0, 10]}}},
        {"$group": {"_id": "$date", "requests": {"$sum": 1}, "tokens": {"$sum": "$total_tokens"}}},
        {"$sort": {"_id": -1}},
        {"$limit": 30}
    ]

    total = await db.usage_logs().aggregate(pipeline_total).to_list(1)
    today = await db.usage_logs().aggregate(pipeline_today).to_list(1)
    daily = await db.usage_logs().aggregate(pipeline_daily).to_list(30)

    t = total[0] if total else {}
    td = today[0] if today else {}

    return {
        "total_requests": t.get("total_requests", 0),
        "total_tokens": t.get("total_tokens", 0),
        "total_prompt_tokens": t.get("total_prompt", 0),
        "total_completion_tokens": t.get("total_completion", 0),
        "avg_response_time_ms": round(t.get("avg_response", 0), 1),
        "requests_today": td.get("count", 0),
        "tokens_today": td.get("tokens", 0),
        "daily_stats": [{"date": d["_id"], "requests": d["requests"], "tokens": d["tokens"]} for d in daily],
        "rag_stats": {
            "total_chunks": vector_store.total_chunks,
            "embedding_model": settings.EMBEDDING_MODEL,
            "index_loaded": vector_store.is_loaded,
        }
    }


@router.post("/rag/index")
async def start_indexing(request: Request, background_tasks: BackgroundTasks, max_docs: int = 50000):
    await validate_admin_token(request)

    if rag_service._indexing:
        return {"status": "already_indexing", "progress": rag_service.index_progress}

    background_tasks.add_task(rag_service.index_dataset, max_docs)
    return {"status": "started", "max_docs": max_docs}


@router.get("/rag/status")
async def rag_status(request: Request):
    await validate_admin_token(request)

    return {
        "total_chunks": vector_store.total_chunks,
        "embedding_model": settings.EMBEDDING_MODEL,
        "index_loaded": vector_store.is_loaded,
        "indexing_progress": rag_service.index_progress,
    }


@router.post("/rag/add-document")
async def add_document(request: Request):
    await validate_admin_token(request)
    body = await request.json()

    title = body.get("title", "")
    content = body.get("content", "")
    doc_type = body.get("doc_type", "legal")

    if not content:
        raise HTTPException(status_code=400, detail={"error": {"message": "Content is required"}})

    chunks_added = rag_service.add_custom_document(title, content, doc_type)

    # Save to MongoDB too
    try:
        await db.documents().insert_one({
            "title": title,
            "doc_type": doc_type,
            "chunk_count": chunks_added,
            "status": "indexed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return {"message": f"Added {chunks_added} chunks", "chunks": chunks_added}


@router.post("/rag/clear")
async def clear_index(request: Request):
    await validate_admin_token(request)
    vector_store.clear()
    return {"message": "Vector store cleared"}

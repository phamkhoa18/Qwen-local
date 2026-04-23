"""
Chat completion routes with RAG - Fixed streaming for Cloudflare
"""
import time
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from backend.models import ChatCompletionRequest
from backend.middleware import get_api_key_from_request
from backend.services.ollama_service import ollama_service
from backend.services.rag_service import rag_service
from backend.database import db
from backend.config import settings

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    start_time = time.time()
    key_doc = await get_api_key_from_request(request)

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    # Get last user message for RAG
    user_message = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_message = m["content"]
            break

    # RAG retrieval
    sources = []
    if body.use_rag and user_message and rag_service.is_ready:
        sources = rag_service.retrieve(user_message, settings.TOP_K)
        if sources:
            augmented = rag_service.build_rag_prompt(user_message, sources)
            for i in range(len(messages) - 1, -1, -1):
                if messages[i]["role"] == "user":
                    messages[i]["content"] = augmented
                    break

    # Add system prompt
    if not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": settings.SYSTEM_PROMPT})

    if body.stream:
        async def generate():
            # Send sources first
            if sources:
                yield f"data: {json.dumps({'sources': sources})}\n\n"

            async for chunk in ollama_service.chat_stream(
                messages=messages,
                model=body.model,
                temperature=body.temperature,
                top_p=body.top_p,
                max_tokens=body.max_tokens or 8192,
                stop=body.stop,
            ):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Transfer-Encoding": "chunked",
            }
        )

    # Non-streaming
    result = await ollama_service.chat(
        messages=messages,
        model=body.model,
        temperature=body.temperature,
        top_p=body.top_p,
        max_tokens=body.max_tokens or 8192,
        stop=body.stop,
    )
    if sources:
        result["sources"] = sources

    # Log usage
    elapsed = int((time.time() - start_time) * 1000)
    try:
        await db.usage_logs().insert_one({
            "api_key_id": str(key_doc["_id"]),
            "api_key_name": key_doc.get("name", ""),
            "model": body.model,
            "prompt_tokens": result["usage"]["prompt_tokens"],
            "completion_tokens": result["usage"]["completion_tokens"],
            "total_tokens": result["usage"]["total_tokens"],
            "response_time_ms": elapsed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": "/v1/chat/completions",
            "used_rag": bool(sources),
        })
    except Exception:
        pass

    return result


@router.get("/v1/models")
async def list_models():
    models = await ollama_service.list_models()
    return {
        "object": "list",
        "data": [{"id": m.get("name", m.get("model", "")), "object": "model", "created": 0, "owned_by": "ollama-local"} for m in models]
    }

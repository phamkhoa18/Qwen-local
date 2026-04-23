"""
Chat completion routes with RAG - mode-aware system prompts
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

    # RAG retrieval (only when use_rag=True)
    sources = []
    if body.use_rag and user_message and rag_service.is_ready:
        search_query = user_message
        
        # --- BƯỚC MỚI: QUERY REFORMULATION (Biến đổi câu hỏi) ---
        # Nếu có lịch sử chat (nhiều hơn 1 tin nhắn), dùng AI để viết lại câu hỏi cho chuẩn ngữ cảnh
        if len(messages) > 1:
            try:
                # Lấy 4 tin nhắn gần nhất để làm ngữ cảnh
                history_context = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in messages[-5:-1]])
                rewrite_prompt = f"""Bạn là một trợ lý AI thông minh. Nhiệm vụ của bạn là đọc lịch sử trò chuyện và viết lại câu hỏi cuối cùng của người dùng thành một câu hỏi DUY NHẤT, đầy đủ ngữ cảnh, rõ nghĩa và độc lập để dùng làm từ khóa tìm kiếm trong thư viện pháp luật.
KHÔNG được trả lời câu hỏi. CHỈ xuất ra câu hỏi đã được viết lại.

Lịch sử trò chuyện:
{history_context}

Câu hỏi cuối của người dùng: {user_message}

Câu hỏi đã viết lại:"""
                
                print(f"[RAG] Đang viết lại câu hỏi để tìm kiếm...")
                rewrite_res = await ollama_service.chat(
                    messages=[{"role": "user", "content": rewrite_prompt}],
                    model=body.model,
                    temperature=0.1,
                    max_tokens=100
                )
                
                if rewrite_res and "choices" in rewrite_res and len(rewrite_res["choices"]) > 0:
                    rewritten = rewrite_res["choices"][0]["message"]["content"].strip()
                    # Loại bỏ ngoặc kép nếu AI sinh ra
                    rewritten = rewritten.strip('"').strip("'")
                    if rewritten and len(rewritten) > 5:
                        search_query = rewritten
                        print(f"[RAG] Đổi câu hỏi: '{user_message}' -> '{search_query}'")
            except Exception as e:
                print(f"[WARN] Lỗi khi viết lại câu hỏi: {e}")
        # ---------------------------------------------------------

        sources = rag_service.retrieve(search_query, settings.TOP_K)
        if sources:
            augmented = rag_service.build_rag_prompt(user_message, sources)
            for i in range(len(messages) - 1, -1, -1):
                if messages[i]["role"] == "user":
                    messages[i]["content"] = augmented
                    break

    # System prompt based on mode:
    # - use_rag=True → Legal system prompt (RAG mode)
    # - use_rag=False → General AI prompt (LLM direct mode)
    if not any(m["role"] == "system" for m in messages):
        if body.use_rag:
            messages.insert(0, {"role": "system", "content": settings.SYSTEM_PROMPT})
        else:
            messages.insert(0, {"role": "system", "content": settings.SYSTEM_PROMPT_GENERAL})

    if body.stream:
        async def generate():
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


@router.post("/v1/documents/search")
async def search_documents(request: Request, body: ChatCompletionRequest):
    """Fast vector search without LLM generation"""
    start_time = time.time()
    await get_api_key_from_request(request)
    
    query = ""
    for m in reversed(body.messages):
        if m.role == "user":
            query = m.content
            break
            
    if not query:
        raise HTTPException(status_code=400, detail="Missing query")
        
    sources = rag_service.retrieve(query, settings.TOP_K)
    return {"sources": sources, "query": query, "time_ms": int((time.time() - start_time) * 1000)}


@router.get("/v1/models")
async def list_models():
    models = await ollama_service.list_models()
    return {
        "object": "list",
        "data": [{"id": m.get("name", m.get("model", "")), "object": "model", "created": 0, "owned_by": "ollama-local"} for m in models]
    }

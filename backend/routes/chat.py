"""
Chat completion routes — Agentic RAG + Multi-LLM
- use_rag=False → Direct chat with Qwen (Hỏi AI trực tiếp) — NO changes
- use_rag=True → Agentic RAG with Hybrid Search + Multi-step reasoning
"""
import time
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from backend.models import ChatCompletionRequest
from backend.middleware import get_api_key_from_request
from backend.services.ollama_service import ollama_service
from backend.services.llm_router import llm_router, is_cloud_model
from backend.services.rag_service import rag_service
from backend.services.agent_service import agent_rag
from backend.database import db
from backend.config import settings

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    start_time = time.time()
    key_doc = await get_api_key_from_request(request)

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    # Get last user message
    user_message = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_message = m["content"]
            break

    # ============================================================
    # MODE 1: "Hỏi AI trực tiếp" (use_rag=False)
    # → Direct chat with Qwen/Cloud model, NO RAG, NO changes
    # ============================================================
    sources = []
    agent_info = None

    if not body.use_rag:
        # General AI mode — add general system prompt
        if not any(m["role"] == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": settings.SYSTEM_PROMPT_GENERAL})

    # ============================================================
    # MODE 2: "Tra cứu & Hỏi đáp" (use_rag=True)
    # → Agentic RAG: multi-step search + cross-reference
    # ============================================================
    elif body.use_rag and user_message and rag_service.is_ready:
        search_query = user_message

        # Query Reformulation (if multi-turn conversation)
        if len(messages) > 1:
            try:
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
                    model=body.model if not is_cloud_model(body.model) else settings.DEFAULT_MODEL,
                    temperature=0.1,
                    max_tokens=100
                )

                if rewrite_res and "choices" in rewrite_res and len(rewrite_res["choices"]) > 0:
                    rewritten = rewrite_res["choices"][0]["message"]["content"].strip().strip('"').strip("'")
                    if rewritten and len(rewritten) > 5:
                        search_query = rewritten
                        print(f"[RAG] Đổi câu hỏi: '{user_message}' -> '{search_query}'")
            except Exception as e:
                print(f"[WARN] Lỗi khi viết lại câu hỏi: {e}")

        # === AGENTIC RAG: Multi-step search + cross-reference ===
        if settings.AGENT_ENABLED:
            print(f"[AGENT] Bắt đầu Agentic RAG cho: '{search_query}'")
            agent_result = agent_rag.process(search_query, messages)
            sources = agent_result["sources"]
            agent_info = {
                "intent": agent_result["intent"],
                "steps": agent_result["steps"],
                "total_sources": agent_result["total_sources"],
            }
            print(f"[AGENT] Intent={agent_result['intent']}, Sources={agent_result['total_sources']}, Steps={len(agent_result['steps'])}")

            # Replace user message with augmented prompt
            if sources:
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i]["role"] == "user":
                        messages[i]["content"] = agent_result["augmented_prompt"]
                        break
        else:
            # Fallback: simple hybrid search (no agent)
            sources = rag_service.retrieve(search_query, settings.TOP_K)
            if sources:
                augmented = rag_service.build_rag_prompt(user_message, sources)
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i]["role"] == "user":
                        messages[i]["content"] = augmented
                        break

        # Add legal system prompt
        if not any(m["role"] == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": settings.SYSTEM_PROMPT})

    # ============================================================
    # SEND TO LLM (via Router: Ollama or OpenRouter)
    # ============================================================

    if body.stream:
        async def generate():
            # Send sources + agent info first
            if sources:
                meta = {"sources": sources}
                if agent_info:
                    meta["agent"] = agent_info
                yield f"data: {json.dumps(meta)}\n\n"

            async for chunk in llm_router.chat_stream(
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
    result = await llm_router.chat(
        messages=messages,
        model=body.model,
        temperature=body.temperature,
        top_p=body.top_p,
        max_tokens=body.max_tokens or 8192,
        stop=body.stop,
    )
    if sources:
        result["sources"] = sources
    if agent_info:
        result["agent"] = agent_info

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
            "agent_intent": agent_info.get("intent") if agent_info else None,
        })
    except Exception:
        pass

    return result


@router.post("/v1/documents/search")
async def search_documents(request: Request, body: ChatCompletionRequest):
    """Hybrid search (FAISS + BM25) without LLM generation"""
    start_time = time.time()
    await get_api_key_from_request(request)

    query = ""
    for m in reversed(body.messages):
        if m.role == "user":
            query = m.content
            break

    if not query:
        raise HTTPException(status_code=400, detail="Missing query")

    # Use agentic search for document search too
    if settings.AGENT_ENABLED:
        result = agent_rag.process(query)
        return {
            "sources": result["sources"],
            "query": query,
            "intent": result["intent"],
            "steps": result["steps"],
            "time_ms": int((time.time() - start_time) * 1000),
        }

    sources = rag_service.retrieve(query, settings.TOP_K)
    return {"sources": sources, "query": query, "time_ms": int((time.time() - start_time) * 1000)}


@router.get("/v1/models")
async def list_models():
    """List all models from Ollama + OpenRouter"""
    models = await llm_router.list_all_models()
    return {
        "object": "list",
        "data": models,
    }

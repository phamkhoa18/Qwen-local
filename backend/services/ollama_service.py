"""
Ollama service - streaming chat completions
Fixed for Cloudflare tunnel compatibility
"""
import httpx
import json
import time
import uuid
from typing import AsyncGenerator, List, Dict
from backend.config import settings


class OllamaService:

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[Dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                if r.status_code == 200:
                    return r.json().get("models", [])
        except Exception:
            pass
        return []

    async def chat(self, messages, model=None, temperature=0.3, top_p=0.8, max_tokens=8192, stop=None):
        model = model or settings.DEFAULT_MODEL
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "top_p": top_p, "num_predict": max_tokens}
        }
        if stop:
            payload["options"]["stop"] = stop

        async with httpx.AsyncClient(timeout=600) as client:
            r = await client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()

        text = data.get("message", {}).get("content", "")
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", len(text) // 4),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", len(text) // 4)
            }
        }

    async def chat_stream(self, messages, model=None, temperature=0.3, top_p=0.8, max_tokens=8192, stop=None) -> AsyncGenerator[str, None]:
        model = model or settings.DEFAULT_MODEL
        chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "top_p": top_p, "num_predict": max_tokens}
        }
        if stop:
            payload["options"]["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        done = data.get("done", False)

                        if content:
                            chunk = json.dumps({
                                "id": chat_id,
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": model,
                                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]
                            })
                            yield f"data: {chunk}\n\n"

                        if done:
                            final = json.dumps({
                                "id": chat_id,
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": model,
                                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                            })
                            yield f"data: {final}\n\n"
                            yield "data: [DONE]\n\n"
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            error_msg = f"Lỗi kết nối đến Qwen3 (Ollama): {str(e)}"
            print(f"[ERROR] {error_msg}")
            error_chunk = json.dumps({
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {"content": f"\n\n**HỆ THỐNG BÁO LỖI:** {error_msg}"}, "finish_reason": "stop"}]
            })
            yield f"data: {error_chunk}\n\n"
            yield "data: [DONE]\n\n"

ollama_service = OllamaService()

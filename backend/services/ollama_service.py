"""
Ollama service - handles communication with Ollama LLM server
Supports streaming and non-streaming chat completions
"""
import httpx
import json
import time
import uuid
from typing import AsyncGenerator, Optional, List, Dict
from datetime import datetime, timezone
from backend.config import settings


class OllamaService:
    """Handles all communication with Ollama"""

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
                    data = r.json()
                    return data.get("models", [])
        except Exception:
            pass
        return []

    async def chat(
        self,
        messages: List[Dict],
        model: str = None,
        temperature: float = 0.3,
        top_p: float = 0.8,
        max_tokens: int = 4096,
        stop: List[str] = None,
    ) -> Dict:
        """Non-streaming chat completion"""
        model = model or settings.DEFAULT_MODEL

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            }
        }
        if stop:
            payload["options"]["stop"] = stop

        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()

        response_text = data.get("message", {}).get("content", "")
        eval_count = data.get("eval_count", len(response_text) // 4)
        prompt_count = data.get("prompt_eval_count", 0)

        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": prompt_count,
                "completion_tokens": eval_count,
                "total_tokens": prompt_count + eval_count
            }
        }

    async def chat_stream(
        self,
        messages: List[Dict],
        model: str = None,
        temperature: float = 0.3,
        top_p: float = 0.8,
        max_tokens: int = 4096,
        stop: List[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion - yields SSE chunks"""
        model = model or settings.DEFAULT_MODEL
        chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            }
        }
        if stop:
            payload["options"]["stop"] = stop

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        done = data.get("done", False)

                        chunk = {
                            "id": chat_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": content} if content else {},
                                "finish_reason": "stop" if done else None
                            }]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

                        if done:
                            yield "data: [DONE]\n\n"
                            break
                    except json.JSONDecodeError:
                        continue


ollama_service = OllamaService()

"""
OpenRouter service — Multi-LLM cloud provider (Claude, GPT-4o, Gemini, etc.)
OpenAI-compatible API, used as cloud fallback / premium model access
"""
import httpx
import json
import time
import uuid
from typing import AsyncGenerator, List, Dict, Optional
from backend.config import settings


# Models available via OpenRouter
OPENROUTER_MODELS = {
    "google/gemini-2.5-flash": {"name": "Gemini 2.5 Flash", "provider": "google"},
    "anthropic/claude-sonnet-4": {"name": "Claude Sonnet 4", "provider": "anthropic"},
    "openai/gpt-4o": {"name": "GPT-4o", "provider": "openai"},
    "openai/gpt-4o-mini": {"name": "GPT-4o Mini", "provider": "openai"},
    "google/gemini-2.5-pro": {"name": "Gemini 2.5 Pro", "provider": "google"},
    "meta-llama/llama-4-maverick": {"name": "Llama 4 Maverick", "provider": "meta"},
}


class OpenRouterService:

    def __init__(self):
        self.base_url = settings.OPENROUTER_BASE_URL
        self.api_key = settings.OPENROUTER_API_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://vks-legal-ai.local",
            "X-Title": "VKS Legal AI Platform",
        }

    async def is_available(self) -> bool:
        if not self.is_configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[Dict]:
        """Return curated list of OpenRouter models"""
        if not self.is_configured:
            return []
        return [
            {"name": model_id, "display_name": info["name"], "provider": info["provider"]}
            for model_id, info in OPENROUTER_MODELS.items()
        ]

    async def chat(self, messages, model=None, temperature=0.3, top_p=0.8, max_tokens=8192, stop=None) -> dict:
        """Non-streaming chat completion via OpenRouter"""
        model = model or settings.OPENROUTER_DEFAULT_MODEL
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if stop:
            payload["stop"] = stop

        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()

        choice = data.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return {
            "id": data.get("id", f"chatcmpl-{uuid.uuid4().hex[:12]}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        }

    async def chat_stream(self, messages, model=None, temperature=0.3, top_p=0.8, max_tokens=8192, stop=None) -> AsyncGenerator[str, None]:
        """Streaming chat completion via OpenRouter"""
        model = model or settings.OPENROUTER_DEFAULT_MODEL
        chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if stop:
            payload["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            finish = data.get("choices", [{}])[0].get("finish_reason")

                            if content:
                                chunk = json.dumps({
                                    "id": chat_id, "object": "chat.completion.chunk",
                                    "created": int(time.time()), "model": model,
                                    "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
                                })
                                yield f"data: {chunk}\n\n"

                            if finish:
                                final = json.dumps({
                                    "id": chat_id, "object": "chat.completion.chunk",
                                    "created": int(time.time()), "model": model,
                                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                                })
                                yield f"data: {final}\n\n"
                                yield "data: [DONE]\n\n"
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            error_msg = f"Lỗi kết nối OpenRouter: {str(e)}"
            print(f"[ERROR] {error_msg}")
            error_chunk = json.dumps({
                "id": chat_id, "object": "chat.completion.chunk",
                "created": int(time.time()), "model": model,
                "choices": [{"index": 0, "delta": {"content": f"\n\n**LỖI:** {error_msg}"}, "finish_reason": "stop"}],
            })
            yield f"data: {error_chunk}\n\n"
            yield "data: [DONE]\n\n"


openrouter_service = OpenRouterService()

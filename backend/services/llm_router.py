"""
LLM Router — Routes between Ollama (local) and OpenRouter (cloud)
Provides unified interface with automatic fallback
"""
from typing import AsyncGenerator, List, Dict, Optional
from backend.config import settings
from backend.services.ollama_service import ollama_service
from backend.services.openrouter_service import openrouter_service, OPENROUTER_MODELS


def is_cloud_model(model: str) -> bool:
    """Check if model ID belongs to OpenRouter (contains '/')"""
    return "/" in model and model in OPENROUTER_MODELS


class LLMRouter:
    """Unified LLM interface: local Ollama or cloud OpenRouter"""

    async def chat(self, messages, model=None, temperature=0.3, top_p=0.8, max_tokens=8192, stop=None) -> dict:
        """Route chat to appropriate provider"""
        model = model or settings.DEFAULT_MODEL

        if is_cloud_model(model):
            if not openrouter_service.is_configured:
                raise Exception("OpenRouter API key not configured")
            return await openrouter_service.chat(
                messages=messages, model=model,
                temperature=temperature, top_p=top_p,
                max_tokens=max_tokens, stop=stop,
            )

        # Default: Ollama local
        try:
            return await ollama_service.chat(
                messages=messages, model=model,
                temperature=temperature, top_p=top_p,
                max_tokens=max_tokens, stop=stop,
            )
        except Exception as e:
            # Fallback to OpenRouter if Ollama fails and OpenRouter is available
            if openrouter_service.is_configured:
                print(f"[WARN] Ollama failed ({e}), falling back to OpenRouter")
                return await openrouter_service.chat(
                    messages=messages, model=settings.OPENROUTER_DEFAULT_MODEL,
                    temperature=temperature, top_p=top_p,
                    max_tokens=max_tokens, stop=stop,
                )
            raise

    async def chat_stream(self, messages, model=None, temperature=0.3, top_p=0.8, max_tokens=8192, stop=None) -> AsyncGenerator[str, None]:
        """Route streaming chat to appropriate provider"""
        model = model or settings.DEFAULT_MODEL

        if is_cloud_model(model):
            if not openrouter_service.is_configured:
                raise Exception("OpenRouter API key not configured")
            async for chunk in openrouter_service.chat_stream(
                messages=messages, model=model,
                temperature=temperature, top_p=top_p,
                max_tokens=max_tokens, stop=stop,
            ):
                yield chunk
            return

        # Default: Ollama local
        try:
            async for chunk in ollama_service.chat_stream(
                messages=messages, model=model,
                temperature=temperature, top_p=top_p,
                max_tokens=max_tokens, stop=stop,
            ):
                yield chunk
        except Exception as e:
            if openrouter_service.is_configured:
                print(f"[WARN] Ollama stream failed ({e}), falling back to OpenRouter")
                async for chunk in openrouter_service.chat_stream(
                    messages=messages, model=settings.OPENROUTER_DEFAULT_MODEL,
                    temperature=temperature, top_p=top_p,
                    max_tokens=max_tokens, stop=stop,
                ):
                    yield chunk
            else:
                raise

    async def list_all_models(self) -> List[Dict]:
        """List models from all providers"""
        models = []

        # Ollama local models
        ollama_models = await ollama_service.list_models()
        for m in ollama_models:
            models.append({
                "id": m.get("name", m.get("model", "")),
                "object": "model",
                "created": 0,
                "owned_by": "ollama-local",
                "provider": "local",
            })

        # OpenRouter cloud models
        if openrouter_service.is_configured:
            cloud_models = await openrouter_service.list_models()
            for m in cloud_models:
                models.append({
                    "id": m["name"],
                    "object": "model",
                    "created": 0,
                    "owned_by": f"openrouter-{m['provider']}",
                    "provider": "cloud",
                    "display_name": m.get("display_name", ""),
                })

        return models


llm_router = LLMRouter()

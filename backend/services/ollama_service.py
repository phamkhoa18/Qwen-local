"""
Ollama service - streaming chat completions with Qwen3 Thinking Mode
Handles <think>...</think> reasoning tags for better accuracy
"""
import httpx
import json
import time
import re
import uuid
from typing import AsyncGenerator, List, Dict
from backend.config import settings


def strip_thinking(text: str) -> tuple:
    """
    Separate <think>reasoning</think> from the final answer.
    Returns (thinking_content, clean_answer)
    """
    thinking = ""
    clean = text

    # Extract all <think> blocks
    think_matches = re.findall(r'<think>(.*?)</think>', text, re.DOTALL)
    if think_matches:
        thinking = "\n".join(m.strip() for m in think_matches)
        clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    return thinking, clean


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

    async def chat(self, messages, model=None, temperature=0.3, top_p=0.8, max_tokens=8192, stop=None, enable_thinking=True):
        """
        Non-streaming chat. enable_thinking=True lets Qwen3 reason before answering.
        The <think> block is stripped from the final response but returned separately.
        """
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

        raw_text = data.get("message", {}).get("content", "")

        # Process thinking
        thinking, clean_text = strip_thinking(raw_text)
        if thinking:
            print(f"[THINK] Qwen3 reasoning: {thinking[:200]}...")

        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": clean_text}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", len(raw_text) // 4),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", len(raw_text) // 4)
            },
            "thinking": thinking if thinking else None,
        }

    async def chat_stream(self, messages, model=None, temperature=0.3, top_p=0.8, max_tokens=8192, stop=None, enable_thinking=True) -> AsyncGenerator[str, None]:
        """
        Streaming chat with Qwen3 Thinking Mode support.
        - <think> blocks are sent as special "thinking" delta events
        - Clean answer tokens are sent as normal "content" delta events
        - Frontend can show/hide thinking separately
        """
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

                    in_thinking = False
                    thinking_buffer = ""
                    sent_thinking_start = False

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            done = data.get("done", False)

                            if content:
                                # Detect <think> opening tag
                                if "<think>" in content:
                                    in_thinking = True
                                    # Remove the <think> tag from content
                                    content = content.replace("<think>", "")
                                    if not sent_thinking_start:
                                        # Signal to frontend that thinking has started
                                        think_signal = json.dumps({
                                            "id": chat_id, "object": "chat.completion.chunk",
                                            "created": int(time.time()), "model": model,
                                            "choices": [{"index": 0, "delta": {"role": "thinking"}, "finish_reason": None}],
                                        })
                                        yield f"data: {think_signal}\n\n"
                                        sent_thinking_start = True

                                # Detect </think> closing tag
                                if "</think>" in content:
                                    in_thinking = False
                                    content = content.replace("</think>", "")
                                    thinking_buffer += content
                                    # Signal thinking ended
                                    think_end = json.dumps({
                                        "id": chat_id, "object": "chat.completion.chunk",
                                        "created": int(time.time()), "model": model,
                                        "choices": [{"index": 0, "delta": {"role": "answer"}, "finish_reason": None}],
                                    })
                                    yield f"data: {think_end}\n\n"
                                    continue

                                if in_thinking:
                                    # Accumulate thinking but don't send as main content
                                    thinking_buffer += content
                                    # Send as thinking delta (frontend can choose to show/hide)
                                    chunk = json.dumps({
                                        "id": chat_id, "object": "chat.completion.chunk",
                                        "created": int(time.time()), "model": model,
                                        "choices": [{"index": 0, "delta": {"thinking": content}, "finish_reason": None}],
                                    })
                                    yield f"data: {chunk}\n\n"
                                else:
                                    # Normal answer content
                                    if content.strip():
                                        chunk = json.dumps({
                                            "id": chat_id, "object": "chat.completion.chunk",
                                            "created": int(time.time()), "model": model,
                                            "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
                                        })
                                        yield f"data: {chunk}\n\n"

                            if done:
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
            error_msg = f"Lỗi kết nối đến Qwen3 (Ollama): {str(e)}"
            print(f"[ERROR] {error_msg}")
            error_chunk = json.dumps({
                "id": chat_id, "object": "chat.completion.chunk",
                "created": int(time.time()), "model": model,
                "choices": [{"index": 0, "delta": {"content": f"\n\n**HỆ THỐNG BÁO LỖI:** {error_msg}"}, "finish_reason": "stop"}],
            })
            yield f"data: {error_chunk}\n\n"
            yield "data: [DONE]\n\n"


ollama_service = OllamaService()

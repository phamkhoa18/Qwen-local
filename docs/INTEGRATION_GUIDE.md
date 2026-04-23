# 🔗 VKS Legal AI — Integration Guide

> Hướng dẫn tích hợp VKS Legal AI API vào ứng dụng của bạn bằng nhiều ngôn ngữ và framework khác nhau.

---

## Mục Lục

- [Tổng Quan](#-tổng-quan)
- [Lấy API Key](#1-lấy-api-key)
- [Python](#2-python)
- [JavaScript / Node.js](#3-javascript--nodejs)
- [cURL](#4-curl)
- [OpenAI SDK (Drop-in Replacement)](#5-openai-sdk-drop-in-replacement)
- [LangChain Integration](#6-langchain-integration)
- [Streaming Best Practices](#7-streaming-best-practices)
- [Multi-turn Conversation](#8-multi-turn-conversation)
- [Xử Lý RAG Sources](#9-xử-lý-rag-sources)
- [Webhook & Automation](#10-webhook--automation)
- [FAQ](#-faq)

---

## 🌐 Tổng Quan

VKS Legal AI cung cấp API **tương thích chuẩn OpenAI**, cho phép bạn tích hợp với bất kỳ ứng dụng nào đã hỗ trợ OpenAI API chỉ bằng cách thay đổi `base_url`.

| Thông tin | Giá trị |
|---|---|
| **Base URL** | `http://your-server:8000` |
| **API Format** | OpenAI-compatible (`/v1/chat/completions`) |
| **Auth** | Bearer Token (`Authorization: Bearer vks-xxx`) |
| **Response Format** | JSON (non-streaming) hoặc SSE (streaming) |
| **Default Model** | `qwen3:30b-a3b` |

---

## 1. Lấy API Key

### Bước 1: Đăng nhập Admin

```bash
curl -X POST http://your-server:8000/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "vks@2024"}'
```

Response:
```json
{"access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer", "expires_in": 86400}
```

### Bước 2: Tạo API Key

```bash
curl -X POST http://your-server:8000/admin/api-keys \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name": "My App", "description": "API key cho ứng dụng XYZ", "rate_limit": 60}'
```

Response:
```json
{
  "id": "663f1a2b...",
  "name": "My App",
  "key": "vks-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4",
  "key_preview": "vks-a1b2...w3x4"
}
```

> ⚠️ **LƯU Ý:** Lưu lại `key` ngay! Nó chỉ hiển thị **1 lần duy nhất** khi tạo.

---

## 2. Python

### Cài đặt

```bash
pip install httpx  # hoặc requests
```

### Chat cơ bản (Non-streaming)

```python
import httpx

BASE_URL = "http://your-server:8000"
API_KEY = "vks-your-api-key"

def chat(question: str, use_rag: bool = True) -> dict:
    """Gửi câu hỏi pháp luật và nhận trả lời"""
    response = httpx.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "qwen3:30b-a3b",
            "messages": [
                {"role": "user", "content": question}
            ],
            "use_rag": use_rag,
            "temperature": 0.3,
            "max_tokens": 4096,
            "stream": False,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()


# Sử dụng
result = chat("Tội trộm cắp tài sản bị xử phạt thế nào?")

# Lấy câu trả lời
answer = result["choices"][0]["message"]["content"]
print("📝 Trả lời:", answer)

# Lấy nguồn trích dẫn (nếu có)
sources = result.get("sources", [])
for src in sources:
    print(f"📚 {src['title']} - {src['article']} (Score: {src['score']})")
```

### Streaming Response

```python
import httpx
import json

def chat_stream(question: str, use_rag: bool = True):
    """Streaming chat — nhận từng token real-time"""
    with httpx.stream(
        "POST",
        f"{BASE_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "qwen3:30b-a3b",
            "messages": [{"role": "user", "content": question}],
            "use_rag": use_rag,
            "stream": True,
        },
        timeout=120.0,
    ) as response:
        response.raise_for_status()
        
        sources = []
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            
            data_str = line[6:]  # Bỏ "data: " prefix
            
            if data_str == "[DONE]":
                break
            
            try:
                data = json.loads(data_str)
                
                # Event đầu: RAG sources
                if "sources" in data and "choices" not in data:
                    sources = data["sources"]
                    continue
                
                # Streaming token
                delta = data["choices"][0]["delta"]
                content = delta.get("content", "")
                if content:
                    print(content, end="", flush=True)
                    
            except json.JSONDecodeError:
                continue
        
        print()  # Newline cuối
        return sources


# Sử dụng
sources = chat_stream("Phân tích Điều 134 Bộ luật Hình sự về tội cố ý gây thương tích")
```

### Async Python

```python
import httpx
import asyncio

async def chat_async(question: str) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "messages": [{"role": "user", "content": question}],
                "use_rag": True,
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()


# Chạy
result = asyncio.run(chat_async("Luật giao thông đường bộ quy định gì?"))
print(result["choices"][0]["message"]["content"])
```

---

## 3. JavaScript / Node.js

### Fetch API (Browser / Node 18+)

```javascript
const BASE_URL = "http://your-server:8000";
const API_KEY = "vks-your-api-key";

// Non-streaming
async function chat(question, useRag = true) {
  const response = await fetch(`${BASE_URL}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "qwen3:30b-a3b",
      messages: [{ role: "user", content: question }],
      use_rag: useRag,
      stream: false,
      temperature: 0.3,
    }),
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.json();
}

// Sử dụng
const result = await chat("Tội lừa đảo chiếm đoạt tài sản?");
console.log("Trả lời:", result.choices[0].message.content);
console.log("Nguồn:", result.sources);
```

### Streaming (Browser / SSE)

```javascript
async function chatStream(question, onToken, onSources) {
  const response = await fetch(`${BASE_URL}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      messages: [{ role: "user", content: question }],
      use_rag: true,
      stream: true,
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop(); // Giữ dòng chưa hoàn chỉnh

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const dataStr = line.slice(6);

      if (dataStr === "[DONE]") return;

      try {
        const data = JSON.parse(dataStr);

        // RAG sources (event đầu tiên)
        if (data.sources && !data.choices) {
          onSources?.(data.sources);
          continue;
        }

        // Streaming token
        const content = data.choices?.[0]?.delta?.content;
        if (content) onToken(content);
      } catch (e) {
        // Bỏ qua JSON parse error
      }
    }
  }
}

// Sử dụng
let fullText = "";
await chatStream(
  "Quyền của bị can theo BLTTHS?",
  (token) => {
    fullText += token;
    document.getElementById("output").textContent = fullText;
  },
  (sources) => {
    console.log("📚 Nguồn tham khảo:", sources);
  }
);
```

### Node.js (axios)

```javascript
const axios = require("axios");

async function chat(question) {
  const { data } = await axios.post(
    `${BASE_URL}/v1/chat/completions`,
    {
      messages: [{ role: "user", content: question }],
      use_rag: true,
      stream: false,
    },
    {
      headers: { Authorization: `Bearer ${API_KEY}` },
      timeout: 120000,
    }
  );
  return data;
}
```

---

## 4. cURL

### Chat (Non-streaming)

```bash
curl -X POST http://your-server:8000/v1/chat/completions \
  -H "Authorization: Bearer vks-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Tội giết người bị xử phạt thế nào?"}],
    "use_rag": true,
    "stream": false
  }'
```

### Chat (Streaming)

```bash
curl -N -X POST http://your-server:8000/v1/chat/completions \
  -H "Authorization: Bearer vks-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Phân tích tội cướp tài sản"}],
    "use_rag": true,
    "stream": true
  }'
```

### Tìm kiếm văn bản (không dùng LLM)

```bash
curl -X POST http://your-server:8000/v1/documents/search \
  -H "Authorization: Bearer vks-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "bảo vệ người tố giác"}]
  }'
```

### Kiểm tra hệ thống

```bash
curl http://your-server:8000/admin/health
```

---

## 5. OpenAI SDK (Drop-in Replacement)

VKS Legal AI **tương thích chuẩn OpenAI**, bạn có thể dùng trực tiếp **OpenAI Python/JS SDK** chỉ cần đổi `base_url`.

### Python (openai SDK)

```bash
pip install openai
```

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://your-server:8000/v1",  # ← Đổi sang VKS server
    api_key="vks-your-api-key",             # ← Dùng VKS API key
)

# Non-streaming
response = client.chat.completions.create(
    model="qwen3:30b-a3b",
    messages=[
        {"role": "user", "content": "Quy định về tội đánh bạc?"}
    ],
    temperature=0.3,
    max_tokens=4096,
    # Lưu ý: use_rag không hỗ trợ qua OpenAI SDK, mặc định = true
)
print(response.choices[0].message.content)

# Streaming
stream = client.chat.completions.create(
    model="qwen3:30b-a3b",
    messages=[
        {"role": "user", "content": "Hình phạt tội buôn bán ma túy?"}
    ],
    stream=True,
)

for chunk in stream:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)
```

### JavaScript (openai SDK)

```bash
npm install openai
```

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://your-server:8000/v1", // ← Đổi sang VKS server
  apiKey: "vks-your-api-key",
});

// Non-streaming
const response = await client.chat.completions.create({
  model: "qwen3:30b-a3b",
  messages: [
    { role: "user", content: "Luật lao động quy định gì về sa thải?" },
  ],
});
console.log(response.choices[0].message.content);

// Streaming
const stream = await client.chat.completions.create({
  model: "qwen3:30b-a3b",
  messages: [{ role: "user", content: "Quyền thừa kế theo pháp luật?" }],
  stream: true,
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || "");
}
```

> 💡 **Lưu ý:** Khi dùng OpenAI SDK, tham số `use_rag` (custom) sẽ mặc định là `true`. Nếu muốn tắt RAG, dùng trực tiếp `httpx`/`fetch` thay vì SDK.

---

## 6. LangChain Integration

```bash
pip install langchain langchain-openai
```

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://your-server:8000/v1",
    api_key="vks-your-api-key",
    model="qwen3:30b-a3b",
    temperature=0.3,
    max_tokens=4096,
    streaming=True,
)

# Invoke
response = llm.invoke("Phân tích Điều 123 BLHS về tội giết người")
print(response.content)

# Streaming
for chunk in llm.stream("Quy định về tội tham ô tài sản?"):
    print(chunk.content, end="", flush=True)
```

---

## 7. Streaming Best Practices

### Xử Lý SSE Event Format

```
data: {"sources": [...]}                         ← Nguồn RAG (event đầu, nếu có)
data: {"choices":[{"delta":{"content":"..."}}]}   ← Từng token
data: {"choices":[{"delta":{},"finish_reason":"stop"}]}  ← Kết thúc
data: [DONE]                                      ← Tín hiệu hoàn tất
```

### Tips

1. **Luôn kiểm tra `[DONE]`** để biết stream đã kết thúc
2. **Buffer dữ liệu** — SSE events có thể bị split giữa các `read()` calls
3. **Timeout dài** — Streaming responses có thể kéo dài 60-120 giây cho câu hỏi phức tạp
4. **Xử lý nguồn trước** — Event `sources` luôn đến đầu tiên, hiển thị nguồn trước khi có câu trả lời

---

## 8. Multi-turn Conversation

Để duy trì ngữ cảnh hội thoại, gửi toàn bộ lịch sử chat trong `messages`:

```python
messages = [
    {"role": "user", "content": "Tội trộm cắp tài sản là gì?"},
    {"role": "assistant", "content": "Theo Điều 173 BLHS 2015..."},
    {"role": "user", "content": "Nếu tài sản trị giá trên 500 triệu thì sao?"},
    # ← AI sẽ hiểu "tài sản" ở đây liên quan đến "tội trộm cắp" ở câu trước
]

response = httpx.post(
    f"{BASE_URL}/v1/chat/completions",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={"messages": messages, "use_rag": True, "stream": False},
)
```

> 💡 **Query Reformulation:** Khi có lịch sử hội thoại (>1 message), hệ thống tự động dùng AI để viết lại câu hỏi cuối cùng cho đầy đủ ngữ cảnh trước khi tìm kiếm RAG.

---

## 9. Xử Lý RAG Sources

### Non-streaming

```python
result = chat("Tội lừa đảo chiếm đoạt tài sản?")

# Trích xuất nguồn
sources = result.get("sources", [])
for i, src in enumerate(sources, 1):
    print(f"[Nguồn {i}] {src['title']} — {src['article']}")
    print(f"  Độ chính xác: {src['score']:.0%}")
    print(f"  Nội dung: {src['content'][:200]}...")
    print()
```

### Streaming

```python
# Trong streaming, sources nằm ở event đầu tiên
# data: {"sources": [...]}

# Sau đó mới đến các token:
# data: {"choices": [{"delta": {"content": "..."}}]}
```

---

## 10. Webhook & Automation

### Tích hợp với Telegram Bot

```python
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters

API_KEY = "vks-your-api-key"
BASE_URL = "http://your-server:8000"

async def handle_message(update: Update, context):
    question = update.message.text
    
    import httpx
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "messages": [{"role": "user", "content": question}],
                "use_rag": True,
                "stream": False,
            },
        )
        result = response.json()
    
    answer = result["choices"][0]["message"]["content"]
    await update.message.reply_text(answer[:4096])  # Telegram limit

app = ApplicationBuilder().token("YOUR_TELEGRAM_BOT_TOKEN").build()
app.add_handler(MessageHandler(filters.TEXT, handle_message))
app.run_polling()
```

### Tích hợp với Discord Bot

```python
import discord
import httpx

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if not message.content.startswith("!hoi "):
        return
    
    question = message.content[5:]
    
    async with httpx.AsyncClient(timeout=120) as http:
        response = await http.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "messages": [{"role": "user", "content": question}],
                "use_rag": True,
                "stream": False,
            },
        )
        result = response.json()
    
    answer = result["choices"][0]["message"]["content"]
    # Discord limit: 2000 chars
    for i in range(0, len(answer), 2000):
        await message.reply(answer[i:i+2000])

client.run("YOUR_DISCORD_BOT_TOKEN")
```

---

## ❓ FAQ

### Q: Tôi có thể dùng OpenAI SDK không?
**A:** Có! Chỉ cần đổi `base_url` sang server VKS. Xem [mục 5](#5-openai-sdk-drop-in-replacement).

### Q: `use_rag` hoạt động thế nào?
**A:** 
- `use_rag: true` — AI sẽ tìm kiếm văn bản pháp luật liên quan trước khi trả lời (Legal RAG mode)
- `use_rag: false` — AI trả lời tự do như ChatGPT (General mode)

### Q: Rate limit là bao nhiêu?
**A:** Mặc định 30 request/phút/key. Admin có thể tùy chỉnh khi tạo key.

### Q: Streaming có khác biệt gì?
**A:** Streaming trả về từng token real-time qua SSE, cho trải nghiệm mượt hơn. Response format tuân theo chuẩn OpenAI streaming.

### Q: Tôi có thể tự thêm văn bản luật không?
**A:** Có! Dùng endpoint `POST /admin/rag/add-document` để thêm văn bản tùy chỉnh vào hệ thống.

### Q: Model nào được khuyến nghị?
**A:** `qwen3:30b-a3b` — Qwen3 30 tỷ tham số với kiến trúc MoE (chỉ kích hoạt 3 tỷ tham số mỗi lần), cân bằng giữa chất lượng và tốc độ.

---

<p align="center">
  <em>VKS Legal AI Platform · Integration Guide v2.0.0</em>
</p>

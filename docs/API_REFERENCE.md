# 📖 VKS Legal AI — API Reference

> **Version:** 2.0.0  
> **Base URL:** `http://your-server:8000`  
> **Interactive Docs:** `http://your-server:8000/docs` (Swagger UI) | `http://your-server:8000/redoc` (ReDoc)

---

## Mục Lục

- [Authentication](#-authentication)
- [Error Handling](#-error-handling)
- [Rate Limiting](#-rate-limiting)
- [Chat Completions API](#1-chat-completions-api)
- [Document Search API](#2-document-search-api)
- [Models API](#3-models-api)
- [Admin — Login](#4-admin-login)
- [Admin — Health Check](#5-health-check)
- [Admin — Usage Statistics](#6-usage-statistics)
- [Admin — API Key Management](#7-api-key-management)
- [Admin — RAG Management](#8-rag-management)
- [Data Models](#-data-models)

---

## 🔐 Authentication

### API Key Authentication

Mọi endpoint chat/search yêu cầu API Key hợp lệ. Key được truyền theo 1 trong 3 cách (ưu tiên từ trên xuống):

| Phương thức | Header / Param | Ví dụ |
|---|---|---|
| **Bearer Token** (khuyến nghị) | `Authorization: Bearer <key>` | `Authorization: Bearer vks-a1b2c3d4e5f6...` |
| **Custom Header** | `X-API-Key: <key>` | `X-API-Key: vks-a1b2c3d4e5f6...` |
| **Query Parameter** | `?api_key=<key>` | `/v1/chat/completions?api_key=vks-a1b2c3d4...` |

### Admin Token Authentication

Các endpoint `/admin/*` (trừ `/admin/login` và `/admin/health`) yêu cầu JWT token:

```
Authorization: Bearer <jwt_token>
```

JWT token nhận được từ endpoint `/admin/login`, có hiệu lực **24 giờ**.

---

## ❌ Error Handling

Tất cả lỗi trả về dạng JSON thống nhất:

```json
{
  "detail": {
    "error": {
      "message": "Mô tả lỗi",
      "type": "error_type",
      "code": "error_code"
    }
  }
}
```

### HTTP Status Codes

| Code | Ý nghĩa | Khi nào |
|------|----------|---------|
| `200` | Success | Request thành công |
| `400` | Bad Request | Thiếu tham số, dữ liệu không hợp lệ |
| `401` | Unauthorized | Thiếu/sai API key hoặc JWT token hết hạn |
| `403` | Forbidden | Không có quyền admin |
| `404` | Not Found | Endpoint/resource không tồn tại |
| `429` | Too Many Requests | Vượt quá rate limit |
| `500` | Internal Server Error | Lỗi server nội bộ |

---

## ⏱ Rate Limiting

- Mỗi API key có giới hạn request/phút (mặc định: **30 req/min**)
- Rate limit được đo bằng sliding window 1 phút
- Khi bị giới hạn, API trả về `429`:

```json
{
  "detail": {
    "error": {
      "message": "Rate limit exceeded. Max 30/min.",
      "type": "rate_limit_error"
    }
  }
}
```

---

## 1. Chat Completions API

### `POST /v1/chat/completions`

API chính để chat với AI. **Tương thích chuẩn OpenAI Chat Completions**, có thêm tính năng RAG pháp luật.

#### Request Headers

```
Authorization: Bearer vks-your-api-key
Content-Type: application/json
```

#### Request Body

```json
{
  "model": "qwen3:30b-a3b",
  "messages": [
    {"role": "system", "content": "Bạn là trợ lý pháp luật"},
    {"role": "user", "content": "Tội trộm cắp tài sản bị xử phạt thế nào?"}
  ],
  "temperature": 0.3,
  "top_p": 0.8,
  "max_tokens": 4096,
  "stream": false,
  "stop": null,
  "use_rag": true
}
```

#### Tham Số Chi Tiết

| Tham số | Kiểu | Mặc định | Bắt buộc | Mô tả |
|---------|-------|----------|----------|-------|
| `model` | `string` | `qwen3:30b-a3b` | ❌ | Tên model Ollama để sử dụng |
| `messages` | `array` | — | ✅ | Mảng tin nhắn hội thoại (xem [ChatMessage](#chatmessage)) |
| `temperature` | `float` | `0.3` | ❌ | Độ sáng tạo (0.0 – 2.0). Giá trị thấp = chính xác hơn |
| `top_p` | `float` | `0.8` | ❌ | Nucleus sampling (0.0 – 1.0) |
| `max_tokens` | `int` | `4096` | ❌ | Số token tối đa cho response (1 – 32768) |
| `stream` | `bool` | `false` | ❌ | Bật streaming response (SSE) |
| `stop` | `array` | `null` | ❌ | Danh sách chuỗi dừng sinh văn bản |
| `use_rag` | `bool` | `true` | ❌ | `true`: RAG pháp luật · `false`: chat tự do (general AI) |

#### Response (Non-Streaming) — `stream: false`

```json
{
  "id": "chatcmpl-a1b2c3d4e5f6",
  "object": "chat.completion",
  "created": 1714000000,
  "model": "qwen3:30b-a3b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Theo Điều 173 Bộ luật Hình sự 2015 (sửa đổi, bổ sung 2017)..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 1250,
    "completion_tokens": 480,
    "total_tokens": 1730
  },
  "sources": [
    {
      "content": "Điều 173. Tội trộm cắp tài sản...",
      "title": "Bộ luật Hình sự 2015",
      "article": "Điều 173",
      "score": 0.8724,
      "doc_type": "legal"
    }
  ]
}
```

#### Response (Streaming) — `stream: true`

Trả về `text/event-stream` theo chuẩn SSE. Mỗi event có format:

```
data: {"sources": [...]}      ← Event đầu tiên (nếu có RAG sources)

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1714000000,"model":"qwen3:30b-a3b","choices":[{"index":0,"delta":{"content":"Theo "},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1714000000,"model":"qwen3:30b-a3b","choices":[{"index":0,"delta":{"content":"Điều "},"finish_reason":null}]}

...

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1714000000,"model":"qwen3:30b-a3b","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

> **Lưu ý:** Khi `use_rag=true` và tìm thấy tài liệu liên quan, event đầu tiên trong stream sẽ chứa trường `sources` (danh sách các đoạn luật đã dùng).

#### Ví Dụ cURL

```bash
# Non-streaming + RAG pháp luật
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer vks-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3:30b-a3b",
    "messages": [
      {"role": "user", "content": "Hình phạt cho tội lừa đảo chiếm đoạt tài sản?"}
    ],
    "use_rag": true,
    "stream": false
  }'

# Streaming + General AI (chat tự do)
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer vks-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Viết cho tôi bài thơ về mùa xuân"}
    ],
    "use_rag": false,
    "stream": true
  }'
```

---

## 2. Document Search API

### `POST /v1/documents/search`

Tìm kiếm văn bản pháp luật **không cần LLM** — chỉ dùng vector similarity search. Nhanh hơn chat completions nhiều lần.

#### Request

```bash
curl -X POST http://localhost:8000/v1/documents/search \
  -H "Authorization: Bearer vks-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "quy định về bảo vệ môi trường"}]
  }'
```

#### Response

```json
{
  "sources": [
    {
      "content": "Điều 235. Tội gây ô nhiễm môi trường...",
      "title": "Bộ luật Hình sự 2015",
      "article": "Điều 235",
      "score": 0.7891,
      "doc_type": "legal"
    },
    {
      "content": "Luật Bảo vệ Môi trường 2020, Chương III...",
      "title": "Luật Bảo vệ Môi trường",
      "article": "Điều 28",
      "score": 0.7456,
      "doc_type": "legal"
    }
  ],
  "query": "quy định về bảo vệ môi trường",
  "time_ms": 42
}
```

---

## 3. Models API

### `GET /v1/models`

Liệt kê tất cả models đang có trên Ollama server. **Không cần authentication.**

#### Response

```json
{
  "object": "list",
  "data": [
    {
      "id": "qwen3:30b-a3b",
      "object": "model",
      "created": 0,
      "owned_by": "ollama-local"
    },
    {
      "id": "llama3:8b",
      "object": "model",
      "created": 0,
      "owned_by": "ollama-local"
    }
  ]
}
```

---

## 4. Admin Login

### `POST /admin/login`

Đăng nhập admin để lấy JWT token.

#### Request

```bash
curl -X POST http://localhost:8000/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "vks@2024"}'
```

#### Response

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

> ⚠️ Token có hiệu lực **24 giờ**. Sau đó cần login lại.

---

## 5. Health Check

### `GET /admin/health`

Kiểm tra trạng thái toàn bộ hệ thống. **Không cần authentication.**

#### Response

```json
{
  "status": "ok",
  "version": "2.0.0",
  "ollama_connected": true,
  "mongodb_connected": true,
  "rag_ready": true,
  "default_model": "qwen3:30b-a3b",
  "total_legal_chunks": 245890,
  "uptime_seconds": 3621.5,
  "indexing": false,
  "indexing_progress": {
    "status": "complete",
    "total_documents": 10000,
    "total_chunks": 245890
  }
}
```

| Trường | Ý nghĩa |
|--------|---------|
| `status` | `ok` = tất cả dịch vụ hoạt động · `degraded` = có dịch vụ bị lỗi |
| `ollama_connected` | Ollama LLM server có kết nối được không |
| `mongodb_connected` | MongoDB có kết nối được không |
| `rag_ready` | Vector store đã load xong, sẵn sàng tìm kiếm |
| `total_legal_chunks` | Tổng số đoạn văn bản pháp luật đã index |
| `indexing` | Có đang chạy tiến trình index hay không |

---

## 6. Usage Statistics

### `GET /admin/usage`

Thống kê sử dụng hệ thống. **Yêu cầu Admin JWT.**

#### Request

```bash
curl http://localhost:8000/admin/usage \
  -H "Authorization: Bearer <admin_jwt_token>"
```

#### Response

```json
{
  "total_requests": 15420,
  "total_tokens": 8234567,
  "total_prompt_tokens": 5123456,
  "total_completion_tokens": 3111111,
  "avg_response_time_ms": 2340.5,
  "requests_today": 234,
  "tokens_today": 125678,
  "daily_stats": [
    {"date": "2026-04-23", "requests": 234, "tokens": 125678},
    {"date": "2026-04-22", "requests": 456, "tokens": 234567}
  ],
  "rag_stats": {
    "total_chunks": 245890,
    "embedding_model": "mainguyen9/vietlegal-harrier-0.6b",
    "index_loaded": true
  }
}
```

---

## 7. API Key Management

### `POST /admin/api-keys` — Tạo API Key

**Yêu cầu Admin JWT.**

#### Request

```bash
curl -X POST http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer <admin_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Frontend App",
    "description": "Key cho ứng dụng web frontend",
    "rate_limit": 60
  }'
```

| Tham số | Kiểu | Mặc định | Bắt buộc | Mô tả |
|---------|-------|----------|----------|-------|
| `name` | `string` | — | ✅ | Tên định danh (1-100 ký tự) |
| `description` | `string` | `""` | ❌ | Mô tả mục đích sử dụng (max 500 ký tự) |
| `rate_limit` | `int` | `30` | ❌ | Giới hạn request/phút |

#### Response

```json
{
  "id": "663f1a2b3c4d5e6f7a8b9c0d",
  "name": "Frontend App",
  "key": "vks-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4",
  "key_preview": "vks-a1b2...w3x4",
  "created_at": "2026-04-23T10:30:00+00:00",
  "is_active": true,
  "rate_limit": 60,
  "description": "Key cho ứng dụng web frontend"
}
```

> ⚠️ **QUAN TRỌNG:** Trường `key` chỉ hiển thị **MỘT LẦN DUY NHẤT** khi tạo. Hãy lưu lại ngay! Sau đó chỉ có thể thấy `key_preview`.

---

### `GET /admin/api-keys` — Liệt Kê API Keys

**Yêu cầu Admin JWT.**

```bash
curl http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer <admin_jwt_token>"
```

#### Response

```json
{
  "keys": [
    {
      "id": "663f1a2b3c4d5e6f7a8b9c0d",
      "name": "Frontend App",
      "key_preview": "vks-a1b2...w3x4",
      "created_at": "2026-04-23T10:30:00+00:00",
      "last_used": "2026-04-23T16:45:00+00:00",
      "is_active": true,
      "rate_limit": 60,
      "total_requests": 1234,
      "description": "Key cho ứng dụng web frontend"
    }
  ],
  "total": 1
}
```

---

### `DELETE /admin/api-keys/{key_id}` — Thu Hồi API Key

**Yêu cầu Admin JWT.** Thu hồi (vô hiệu hóa) API key — key bị revoke sẽ không thể sử dụng lại.

```bash
curl -X DELETE http://localhost:8000/admin/api-keys/663f1a2b3c4d5e6f7a8b9c0d \
  -H "Authorization: Bearer <admin_jwt_token>"
```

#### Response

```json
{
  "message": "API key revoked"
}
```

---

## 8. RAG Management

### `POST /admin/rag/index` — Bắt Đầu Index Dataset

**Yêu cầu Admin JWT.** Tải và index bộ dữ liệu pháp luật từ HuggingFace (chạy nền).

```bash
curl -X POST "http://localhost:8000/admin/rag/index?max_docs=50000" \
  -H "Authorization: Bearer <admin_jwt_token>"
```

| Query Param | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `max_docs` | `int` | `50000` | Số lượng văn bản tối đa cần index |

#### Response

```json
{
  "status": "started",
  "max_docs": 50000
}
```

Nếu đang index:
```json
{
  "status": "already_indexing",
  "progress": {
    "status": "embedding",
    "current": 12345,
    "total": 50000
  }
}
```

---

### `GET /admin/rag/status` — Trạng Thái RAG

**Yêu cầu Admin JWT.**

```bash
curl http://localhost:8000/admin/rag/status \
  -H "Authorization: Bearer <admin_jwt_token>"
```

#### Response

```json
{
  "total_chunks": 245890,
  "embedding_model": "mainguyen9/vietlegal-harrier-0.6b",
  "index_loaded": true,
  "indexing_progress": {
    "status": "complete",
    "total_documents": 10000,
    "total_chunks": 245890
  }
}
```

**Trạng thái `status`:**

| Giá trị | Ý nghĩa |
|---------|---------|
| `idle` | Chưa bắt đầu index |
| `downloading` | Đang tải dataset từ HuggingFace |
| `processing` | Đang xử lý và chunk văn bản |
| `embedding` | Đang nhúng vector (bước lâu nhất) |
| `complete` | Index hoàn tất |
| `error` | Có lỗi xảy ra |

---

### `POST /admin/rag/add-document` — Thêm Tài Liệu Thủ Công

**Yêu cầu Admin JWT.** Thêm một văn bản pháp luật tùy chỉnh vào vector store.

```bash
curl -X POST http://localhost:8000/admin/rag/add-document \
  -H "Authorization: Bearer <admin_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Nghị định 100/2019/NĐ-CP",
    "content": "Điều 5. Xử phạt người điều khiển xe ô tô...",
    "doc_type": "legal"
  }'
```

| Tham số | Kiểu | Mặc định | Bắt buộc | Mô tả |
|---------|-------|----------|----------|-------|
| `title` | `string` | `""` | ❌ | Tiêu đề văn bản |
| `content` | `string` | — | ✅ | Nội dung văn bản |
| `doc_type` | `string` | `legal` | ❌ | Loại tài liệu (`legal`, `custom`, ...) |

#### Response

```json
{
  "message": "Added 12 chunks",
  "chunks": 12
}
```

---

### `POST /admin/rag/clear` — Xóa Toàn Bộ Index

**Yêu cầu Admin JWT.** ⚠️ **CẢNH BÁO:** Hành động không thể hoàn tác!

```bash
curl -X POST http://localhost:8000/admin/rag/clear \
  -H "Authorization: Bearer <admin_jwt_token>"
```

#### Response

```json
{
  "message": "Vector store cleared"
}
```

---

## 📋 Data Models

### ChatMessage

```json
{
  "role": "user | assistant | system",
  "content": "Nội dung tin nhắn"
}
```

| Role | Mô tả |
|------|--------|
| `system` | Prompt hệ thống (nếu không truyền, server tự thêm dựa trên `use_rag`) |
| `user` | Tin nhắn của người dùng |
| `assistant` | Tin nhắn trước đó của AI (dùng cho multi-turn conversation) |

### RAGSource

```json
{
  "content": "Nội dung đoạn luật đã truy xuất",
  "title": "Tên văn bản pháp luật",
  "article": "Điều XXX",
  "score": 0.8724,
  "doc_type": "legal"
}
```

| Trường | Mô tả |
|--------|--------|
| `content` | Nội dung đoạn văn bản pháp luật |
| `title` | Tên văn bản gốc |
| `article` | Điều/Khoản cụ thể |
| `score` | Độ tương đồng (0.0 – 1.0, càng cao càng liên quan) |
| `doc_type` | Loại tài liệu |

### UsageInfo

```json
{
  "prompt_tokens": 1250,
  "completion_tokens": 480,
  "total_tokens": 1730
}
```

---

## 🔧 Swagger / ReDoc

Ngoài tài liệu này, server còn cung cấp:

- **Swagger UI**: `http://your-server:8000/docs` — Giao diện thử nghiệm API trực tiếp
- **ReDoc**: `http://your-server:8000/redoc` — Tài liệu API dạng đọc

---

<p align="center">
  <em>VKS Legal AI Platform · API Reference v2.0.0</em>
</p>

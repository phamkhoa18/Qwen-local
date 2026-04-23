"""
Pydantic models for VKS Legal AI Platform
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============ Chat Models (OpenAI Compatible) ============

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="qwen3:30b-a3b")
    messages: List[ChatMessage] = Field(..., description="Chat messages")
    temperature: Optional[float] = Field(default=0.3, ge=0, le=2)
    top_p: Optional[float] = Field(default=0.8, ge=0, le=1)
    max_tokens: Optional[int] = Field(default=4096, ge=1, le=32768)
    stream: Optional[bool] = Field(default=False)
    stop: Optional[List[str]] = None
    use_rag: Optional[bool] = Field(default=True, description="Enable RAG retrieval")


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class RAGSource(BaseModel):
    content: str
    score: float
    metadata: Dict[str, Any] = {}


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: UsageInfo
    sources: Optional[List[RAGSource]] = None


# ============ API Key Models ============

class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    rate_limit: Optional[int] = Field(default=30)
    description: Optional[str] = Field(default="", max_length=500)


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key: Optional[str] = None
    key_preview: str
    created_at: str
    last_used: Optional[str] = None
    is_active: bool = True
    rate_limit: int = 30
    total_requests: int = 0
    description: str = ""


class APIKeyListResponse(BaseModel):
    keys: List[APIKeyResponse]
    total: int


# ============ Admin Models ============

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400


# ============ Usage Models ============

class UsageStats(BaseModel):
    total_requests: int = 0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    avg_response_time_ms: float = 0
    requests_today: int = 0
    tokens_today: int = 0
    top_models: List[Dict[str, Any]] = []
    daily_stats: List[Dict[str, Any]] = []


# ============ Model Info ============

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "vks-local"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


# ============ RAG / Document Models ============

class DocumentUpload(BaseModel):
    title: str
    content: str
    doc_type: Optional[str] = "legal"
    metadata: Optional[Dict[str, Any]] = {}


class DocumentResponse(BaseModel):
    id: str
    title: str
    doc_type: str
    chunk_count: int
    status: str
    created_at: str


class RAGStatusResponse(BaseModel):
    total_documents: int
    total_chunks: int
    embedding_model: str
    index_loaded: bool


# ============ Conversation Models ============

class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int


# ============ General ============

class ErrorResponse(BaseModel):
    error: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    ollama_connected: bool
    mongodb_connected: bool
    rag_ready: bool
    default_model: str
    total_legal_chunks: int = 0

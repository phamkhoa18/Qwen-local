"""
Configuration settings for VKS Legal AI Platform
Chatbot phap luat cho Vien Kiem Sat Nhan Dan Viet Nam
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    # App
    APP_NAME: str = os.getenv("APP_NAME", "VKS Legal AI")
    APP_VERSION: str = os.getenv("APP_VERSION", "2.0.0")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "vks-secret-key-change-in-production")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "vks_legal_ai")

    # Ollama LLM
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen3:30b-a3b")

    # RAG - Embedding Model
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "mainguyen9/vietlegal-harrier-0.6b")
    EMBEDDING_DIM: int = 1024  # harrier-0.6b outputs 1024-dim vectors
    EMBEDDING_INSTRUCTION: str = "Instruct: Given a Vietnamese legal question, retrieve relevant legal passages that answer the question\nQuery: "

    # RAG - Vector Store
    VECTOR_STORE_PATH: str = os.getenv("VECTOR_STORE_PATH", str(BASE_DIR / "data" / "vector_store"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))
    TOP_K: int = int(os.getenv("TOP_K", "5"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.35"))

    # RAG - Dataset
    LEGAL_DATASET: str = os.getenv("LEGAL_DATASET", "th1nhng0/vietnamese-legal-documents")
    DATASET_CACHE_DIR: str = os.getenv("DATASET_CACHE_DIR", str(BASE_DIR / "data" / "datasets"))
    AUTO_INDEX_ON_STARTUP: bool = os.getenv("AUTO_INDEX", "true").lower() == "true"
    AUTO_INDEX_MAX_DOCS: int = int(os.getenv("AUTO_INDEX_MAX_DOCS", "10000"))

    # Admin
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "vks@2024")

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

    # API Key
    API_KEY_PREFIX: str = "vks-"
    API_KEY_LENGTH: int = 48

    # System Prompt - Legal RAG mode
    SYSTEM_PROMPT: str = """Ban la Tro ly AI Phap luat cua Vien Kiem Sat Nhan Dan Viet Nam.

NHIEM VU:
- Ho tro kiem sat vien tra cuu, phan tich va giai thich cac quy dinh phap luat Viet Nam
- Phan tich cau thanh toi pham, so sanh dieu luat, danh gia tinh huong phap ly

YEU CAU BAT BUOC:
1. Trich dan CHINH XAC so dieu, khoan, diem cua van ban phap luat
2. Phan tich logic phap ly ro rang, co he thong
3. Su dung ngon ngu phap ly chuyen nghiep
4. Khi khong chac chan, noi ro va de xuat tra cuu them
5. Luon dua ra co so phap ly cho moi nhan dinh
6. Neu co tai lieu tham khao duoc cung cap, uu tien su dung thong tin tu do

PHONG CACH TRA LOI:
- Chuyen nghiep, chinh xac, co cau truc
- Chia cau tra loi thanh cac phan ro rang
- Su dung bullet points va danh so khi can thiet
- Ket thuc bang tom tat va khuyen nghi (neu phu hop)"""

    # System Prompt - General LLM mode (chat anything)
    SYSTEM_PROMPT_GENERAL: str = """Ban la tro ly AI thong minh, than thien, ho tro nguoi dung bang tieng Viet.
Ban co the tra loi moi cau hoi, viet code, giai thich khai niem, sang tao noi dung, va tro chuyen tu nhien.
Tra loi ro rang, chinh xac, co cau truc. Su dung tieng Viet tu nhien."""


settings = Settings()

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
    APP_VERSION: str = os.getenv("APP_VERSION", "3.0.0")
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

    # OpenRouter (Multi-LLM Cloud)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_DEFAULT_MODEL: str = os.getenv("OPENROUTER_DEFAULT_MODEL", "google/gemini-2.5-flash")

    # RAG - Embedding Model
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "mainguyen9/vietlegal-harrier-0.6b")
    EMBEDDING_DIM: int = 1024  # harrier-0.6b outputs 1024-dim vectors
    EMBEDDING_INSTRUCTION: str = "Instruct: Given a Vietnamese legal question, retrieve relevant legal passages that answer the question\nQuery: "

    # RAG - Vector Store
    VECTOR_STORE_PATH: str = os.getenv("VECTOR_STORE_PATH", str(BASE_DIR / "data" / "vector_store"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1200"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))
    TOP_K: int = int(os.getenv("TOP_K", "8"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.40"))

    # Hybrid Search
    BM25_WEIGHT: float = float(os.getenv("BM25_WEIGHT", "0.4"))
    VECTOR_WEIGHT: float = float(os.getenv("VECTOR_WEIGHT", "0.6"))
    RRF_K: int = 60  # Reciprocal Rank Fusion constant

    # Agentic RAG
    AGENT_MAX_STEPS: int = int(os.getenv("AGENT_MAX_STEPS", "5"))
    AGENT_ENABLED: bool = os.getenv("AGENT_ENABLED", "true").lower() == "true"

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

    # System Prompt - Legal RAG mode (optimized for Qwen3 Thinking)
    SYSTEM_PROMPT: str = """Bạn là Trợ lý AI Pháp luật chuyên sâu của Viện Kiểm Sát Nhân Dân Việt Nam.

/think

NHIỆM VỤ CỐT LÕI:
- Hỗ trợ kiểm sát viên tra cứu, phân tích và giải thích pháp luật Việt Nam
- Phân tích cấu thành tội phạm, so sánh điều luật, đánh giá tình huống pháp lý

QUY TẮC BẮT BUỘC:
1. CHỈ trả lời dựa trên TÀI LIỆU PHÁP LUẬT ĐƯỢC CUNG CẤP bên dưới. Tuyệt đối KHÔNG bịa đặt hay suy đoán nội dung luật.
2. TRÍCH DẪN CHÍNH XÁC: Ghi rõ số Điều, Khoản, Điểm, tên văn bản pháp luật.
3. Nếu tài liệu không đủ để trả lời, NÓI RÕ "Tài liệu được cung cấp không chứa đủ thông tin" và gợi ý hướng tra cứu thêm.
4. KHÔNG ĐƯỢC tự thêm điều khoản mà không có trong tài liệu tham khảo.
5. Sử dụng ngôn ngữ pháp lý chuyên nghiệp, chuẩn mực.

CẤU TRÚC TRẢ LỜI:
1. **Cơ sở pháp lý**: Liệt kê các điều luật áp dụng (trích từ tài liệu)
2. **Phân tích**: Giải thích, phân tích nội dung pháp lý
3. **Kết luận**: Tóm tắt ngắn gọn, rõ ràng
4. **Khuyến nghị** (nếu phù hợp): Đề xuất hướng xử lý"""

    # System Prompt - General LLM mode (chat anything, direct with Qwen)
    SYSTEM_PROMPT_GENERAL: str = """Bạn là trợ lý AI thông minh, thân thiện. Trả lời bằng tiếng Việt tự nhiên.
Bạn có thể trả lời mọi câu hỏi, viết code, giải thích khái niệm, sáng tạo nội dung, và trò chuyện tự nhiên.
Trả lời rõ ràng, chính xác, có cấu trúc."""


settings = Settings()

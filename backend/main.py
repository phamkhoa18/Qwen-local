"""
VKS Legal AI Platform - Main Application
Auto-loads legal dataset on first startup
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path

from backend.config import settings
from backend.database import db
from backend.routes import chat, api_keys, admin
from backend.services.rag_service import rag_service

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATES_DIR = FRONTEND_DIR / "templates"


async def auto_index_background():
    """Auto-download and index legal dataset in background"""
    try:
        print("[AUTO-INDEX] Bắt đầu tải dataset pháp luật từ HuggingFace...")
        print(f"[AUTO-INDEX] Dataset: {settings.LEGAL_DATASET}")
        print(f"[AUTO-INDEX] Số lượng tối đa: {settings.AUTO_INDEX_MAX_DOCS}")
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: asyncio.run(rag_service.index_dataset(settings.AUTO_INDEX_MAX_DOCS))
        )
    except Exception as e:
        print(f"[AUTO-INDEX ERROR] {e}")
        # Try sync version
        try:
            import threading
            def index_sync():
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(rag_service.index_dataset(settings.AUTO_INDEX_MAX_DOCS))
                loop.close()
            t = threading.Thread(target=index_sync, daemon=True)
            t.start()
            print("[AUTO-INDEX] Đang chạy nền trong thread riêng...")
        except Exception as e2:
            print(f"[AUTO-INDEX ERROR] Thread cũng lỗi: {e2}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"""
==============================================
  VKS LEGAL AI v{settings.APP_VERSION}
  Chatbot Phap Luat - Vien Kiem Sat Nhan Dan
----------------------------------------------
  API:        http://{settings.HOST}:{settings.PORT}
  Playground: http://{settings.HOST}:{settings.PORT}
  Docs:       http://{settings.HOST}:{settings.PORT}/docs
  Ollama:     {settings.OLLAMA_BASE_URL}
  MongoDB:    {settings.MONGODB_URI}
  Embedding:  {settings.EMBEDDING_MODEL}
==============================================
    """)

    await db.connect()

    # Load existing vector store
    loaded = rag_service.initialize()

    # Auto-index if no data exists and auto-index is enabled
    if not loaded and settings.AUTO_INDEX_ON_STARTUP:
        print("[INFO] Chưa có dữ liệu pháp luật. Tự động tải và index...")
        import threading
        def bg_index():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(rag_service.index_dataset(settings.AUTO_INDEX_MAX_DOCS))
            except Exception as e:
                print(f"[AUTO-INDEX ERROR] {e}")
            finally:
                loop.close()
        t = threading.Thread(target=bg_index, daemon=True)
        t.start()
        print("[INFO] Dataset đang được tải nền. Server vẫn hoạt động bình thường.")
    elif loaded:
        print(f"[OK] Đã load {rag_service._index_progress.get('total_chunks', 'N/A')} đoạn văn bản pháp luật.")

    yield
    await db.disconnect()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Chatbot AI Phap Luat cho Vien Kiem Sat Nhan Dan Viet Nam",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.include_router(chat.router, tags=["Chat"])
app.include_router(api_keys.router, tags=["API Keys"])
app.include_router(admin.router, tags=["Admin"])


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "default_model": settings.DEFAULT_MODEL
    })


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse(status_code=404, content={"error": {"message": "Not found"}})


@app.exception_handler(500)
async def server_error(request: Request, exc):
    return JSONResponse(status_code=500, content={"error": {"message": "Internal server error"}})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)

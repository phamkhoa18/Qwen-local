"""
VKS Legal AI Platform - Main Application
Chatbot phap luat cho Vien Kiem Sat voi RAG + Qwen3
"""
import time
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
    rag_service.initialize()
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

# Ensure static dir exists
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

import asyncio
import logging
import os
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.exams import router as exam_router
from app.api.v1.jobs import router as job_router
from app.api.v1.sources import router as sources_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.automation import router as automation_router
from app.core.config import settings
from app.core.database import Base, engine

logger = logging.getLogger(__name__)


async def keep_alive_worker():
    """Render instance ko sleep mode me jane se rokne ke liye self-ping background worker"""
    render_url = os.getenv("RENDER_EXTERNAL_URL", "https://niyogdisha.onrender.com")
    health_url = f"{render_url.rstrip('/')}/health"

    # Server start hone ke 60 seconds baad ping shuru karega
    await asyncio.sleep(60)

    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                # Har 10 minute (600s) me ping karega
                await asyncio.sleep(600)
                resp = await client.get(health_url)
                logger.info(f"[Keep-Alive] Pinged {health_url} - Status: {resp.status_code}")
            except Exception as e:
                logger.warning(f"[Keep-Alive] Self ping warning: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Safe Auto-create tables on startup
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Database connection failed during startup: {e}")

    # 2. Start keep-alive background task
    ping_task = asyncio.create_task(keep_alive_worker())

    yield

    # 3. Shutdown: cancel background task
    ping_task.cancel()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-grade API for All India Government Jobs & Exam Lifecycle Portal",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(job_router, prefix=settings.API_V1_STR)
app.include_router(exam_router, prefix=settings.API_V1_STR)
app.include_router(sources_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(ingestion_router, prefix=settings.API_V1_STR)
app.include_router(automation_router, prefix="/api/v1")



@app.get("/", tags=["Root"])
async def root():
    return {
        "success": True,
        "service": settings.PROJECT_NAME,
        "tagline": settings.TAGLINE,
        "documentation": "/docs",
        "health_check": "/health",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "tagline": settings.TAGLINE,
        "version": "1.0.0",
    }

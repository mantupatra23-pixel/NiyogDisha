import asyncio
import logging
import os
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import admin, admit_cards, answer_keys, auth, jobs, results, sources
from app.core.config import settings
from app.core.database import Base, engine

logger = logging.getLogger(__name__)

async def keep_alive():
    """Render instance ko sleep mode me jane se rokne ke liye self-ping worker"""
    render_url = os.getenv("RENDER_EXTERNAL_URL", "https://niyogdisha.onrender.com")
    health_url = f"{render_url.rstrip('/')}/health"
    
    # Instance boot hone ke baad 60 seconds wait karega
    await asyncio.sleep(60)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                # Har 10 minute (600 seconds) me self ping karega
                await asyncio.sleep(600)
                resp = await client.get(health_url)
                logger.info(f"[Keep-Alive] Pinged {health_url} - Status: {resp.status_code}")
            except Exception as e:
                logger.error(f"[Keep-Alive] Error pinging self: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe Auto-create tables on startup
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created successfully")
    except Exception as e:
        logger.error(f"Database connection failed during startup: {e}")
    
    # Start keep-alive background task
    ping_task = asyncio.create_task(keep_alive())
    yield
    # Cancel task on shutdown
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
    allow_origins=settings.cors_origins_list if hasattr(settings, "cors_origins_list") else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes / Routers
api_prefix = getattr(settings, "API_V1_STR", "/api/v1")
app.include_router(auth.router, prefix=api_prefix)
app.include_router(jobs.router, prefix=api_prefix)
app.include_router(admit_cards.router, prefix=api_prefix)
app.include_router(answer_keys.router, prefix=api_prefix)
app.include_router(results.router, prefix=api_prefix)
app.include_router(sources.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)

@app.get("/", tags=["Root"])
async def root():
    return {
        "success": True,
        "service": settings.PROJECT_NAME,
        "tagline": getattr(settings, "TAGLINE", "All India Government Jobs & Exam Lifecycle Portal"),
        "documentation": "/docs",
        "health_check": "/health",
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "tagline": getattr(settings, "TAGLINE", "All India Government Jobs & Exam Lifecycle Portal"),
        "version": "1.0.0",
    }

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.exams import router as exam_router
from app.api.v1.jobs import router as job_router
from app.api.v1.sources import router as sources_router
from app.core.config import settings
from app.core.database import Base, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe Auto-create tables on startup
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Database connection failed during startup: {e}")
    yield


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

# Routes
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(job_router, prefix=settings.API_V1_STR)
app.include_router(exam_router, prefix=settings.API_V1_STR)
app.include_router(sources_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)


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

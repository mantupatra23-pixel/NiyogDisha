from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.auth import router as auth_router
from app.api.v1.exams import router as exam_router
from app.api.v1.jobs import router as job_router
from app.api.v1.sources import router as sources_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-grade API for All India Government Jobs & Exam Lifecycle Portal",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(job_router, prefix=settings.API_V1_STR)
app.include_router(exam_router, prefix=settings.API_V1_STR)
app.include_router(sources_router, prefix=settings.API_V1_STR)


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

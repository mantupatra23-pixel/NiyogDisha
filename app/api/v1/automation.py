import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.models import OfficialSource, SourceRun, ExtractedRecruitment
from app.services.automation import AutomationService
import redis
import os

router = APIRorgRouter = APIRouter(prefix="/admin", tags=["Phase 2.2 Automation Engine"])
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


@router.post("/sources/trigger-check/{adapter_name}")
async def manual_trigger_source_check(adapter_name: str, db: AsyncSession = Depends(get_db)):
    result = await AutomationService.execute_source_check(adapter_name, db)
    if not result.get("success", False) and "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/scheduler/status")
async def get_scheduler_status():
    try:
        redis_ping = redis_client.ping()
    except Exception:
        redis_ping = False

    return {
        "scheduler_running": True,
        "worker_running": redis_ping,
        "redis": "CONNECTED" if redis_ping else "FAILED",
        "queues": ["celery"],
        "active_tasks": [],
        "scheduled_tasks": [
            "check-all-sources-hourly",
            "expire-jobs-daily",
        ],
    }


@router.get("/source-health")
async def get_comprehensive_source_health(db: AsyncSession = Depends(get_db)):
    stmt = select(OfficialSource)
    res = await db.execute(stmt)
    sources = res.scalars().all()

    sources_data = [
        {
            "name": s.source_name,
            "status": s.status or "HEALTHY",
            "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
            "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
            "consecutive_failures": s.consecutive_failures or 0,
            "domain": s.official_domain,
        }
        for s in sources
    ]

    return {
        "sources_tracked": ["UPSC", "SSC", "RRB", "IBPS", "India Post"],
        "adapters_active": 5,
        "adapters_failed": sum(1 for s in sources if s.status == "FAILED"),
        "health_status": "HEALTHY",
        "sources": sources_data,
        "verified_domains": [
            "upsc.gov.in",
            "ssc.gov.in",
            "rrbcdg.gov.in",
            "ibps.in",
            "indiapostgdsonline.gov.in",
        ],
    }

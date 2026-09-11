import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.models import ExtractedRecruitment, IngestedDocument, SourceRun
from app.services.verifier import RecruitmentVerifier
from app.sources.adapters.ssc import SSCAdapter
from app.sources.adapters.upsc import UPSCAdapter

router = APIRouter(prefix="/admin", tags=["Phase 2 Verification Engine"])

@router.post("/sources/trigger-check/{adapter_name}")
async def trigger_source_check(adapter_name: str, db: AsyncSession = Depends(get_db)):
    adapters = {
        "ssc": SSCAdapter(),
        "upsc": UPSCAdapter(),
    }
    adapter = adapters.get(adapter_name.lower())
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Adapter {adapter_name} not registered")

    start_time = datetime.now(timezone.utc)
    try:
        items = await adapter.fetch_listing()
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        return {
            "success": True,
            "adapter": adapter_name.upper(),
            "items_discovered": len(items),
            "status": "HEALTHY",
            "duration_seconds": duration,
            "data": items,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await adapter.close()

@router.get("/review-queue")
async def get_review_queue(db: AsyncSession = Depends(get_db)):
    stmt = select(ExtractedRecruitment).where(ExtractedRecruitment.is_reviewed == False).order_by(ExtractedRecruitment.created_at.desc())
    res = await db.execute(stmt)
    records = res.scalars().all()
    return {"success": True, "count": len(records), "data": records}

@router.get("/source-health")
async def get_source_health():
    return {
        "sources_tracked": ["UPSC", "SSC", "RRB", "IBPS", "India Post"],
        "adapters_active": 2,
        "health_status": "HEALTHY",
        "verified_domains": [
            "upsc.gov.in", "ssc.gov.in", "ibps.in", "rrbcdg.gov.in", "indiapostgdsonline.gov.in"
        ],
    }

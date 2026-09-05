from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.job import JobCreate, JobDetail, PaginatedResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["Government Jobs"])


@router.get("", response_model=PaginatedResponse)
async def get_jobs(
    q: Optional[str] = Query(None, description="Search keyword (UPSC, SSC, Clerk, etc.)"),
    job_type: Optional[str] = Query(None, description="CENTRAL or STATE"),
    closing_soon: bool = Query(False, description="Filter jobs expiring soon"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = JobService(db)
    return await service.list_jobs(q=q, job_type=job_type, closing_soon=closing_soon, page=page, page_size=page_size)


@router.get("/{slug}", response_model=JobDetail)
async def get_job_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    service = JobService(db)
    job = await service.get_by_slug(slug)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("", response_model=JobDetail, status_code=status.HTTP_201_CREATED)
async def create_job(payload: JobCreate, db: AsyncSession = Depends(get_db)):
    service = JobService(db)
    return await service.create_job(payload)

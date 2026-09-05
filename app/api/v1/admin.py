import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.models import (
    AuditLog,
    Job,
    JobCategory,
    JobStatus,
    OfficialSource,
    Organization,
    Qualification,
    State,
)

router = APIRouter(prefix="/admin", tags=["Admin Review Workflow"])


class RejectRequest(BaseModel):
    reason: str


class AdminDashboardStats(BaseModel):
    total_jobs: int
    pending_review: int
    verified: int
    published: int
    expired: int
    active_sources: int


@router.get("/dashboard", response_model=AdminDashboardStats)
async def get_admin_dashboard(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(Job.id))) or 0
    pending = await db.scalar(select(func.count(Job.id)).where(Job.status == JobStatus.PENDING_REVIEW)) or 0
    verified = await db.scalar(select(func.count(Job.id)).where(Job.status == JobStatus.VERIFIED)) or 0
    published = await db.scalar(select(func.count(Job.id)).where(Job.status == JobStatus.PUBLISHED)) or 0
    expired = await db.scalar(select(func.count(Job.id)).where(Job.status == JobStatus.EXPIRED)) or 0
    sources = await db.scalar(select(func.count(OfficialSource.id)).where(OfficialSource.active == True)) or 0

    return AdminDashboardStats(
        total_jobs=total,
        pending_review=pending,
        verified=verified,
        published=published,
        expired=expired,
        active_sources=sources,
    )


@router.get("/pending")
async def get_pending_jobs(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.PENDING_REVIEW)
        .order_by(Job.created_at.desc())
    )
    res = await db.execute(stmt)
    jobs = res.scalars().all()
    return {"success": True, "count": len(jobs), "data": jobs}


@router.post("/jobs/{job_id}/approve")
async def approve_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = JobStatus.VERIFIED
    job.updated_at = datetime.now(timezone.utc)

    # Audit log
    audit = AuditLog(
        action="APPROVE",
        entity_type="JOB",
        entity_id=str(job.id),
        details="Recruitment verified and marked ready for publish.",
    )
    db.add(audit)
    await db.commit()
    return {"success": True, "message": "Job successfully marked as VERIFIED"}


@router.post("/jobs/{job_id}/publish")
async def publish_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = JobStatus.PUBLISHED
    job.published_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)

    # Audit log
    audit = AuditLog(
        action="PUBLISH",
        entity_type="JOB",
        entity_id=str(job.id),
        details="Recruitment published live to public portal.",
    )
    db.add(audit)
    await db.commit()
    return {"success": True, "message": "Job successfully PUBLISHED"}


@router.post("/jobs/{job_id}/reject")
async def reject_job(job_id: uuid.UUID, payload: RejectRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = JobStatus.REJECTED
    job.updated_at = datetime.now(timezone.utc)

    # Audit log
    audit = AuditLog(
        action="REJECT",
        entity_type="JOB",
        entity_id=str(job.id),
        details=f"Reason: {payload.reason}",
    )
    db.add(audit)
    await db.commit()
    return {"success": True, "message": "Job REJECTED successfully"}


@router.post("/seed-master-data")
async def seed_master_data(db: AsyncSession = Depends(get_db)):
    # Master data verification check
    existing = await db.scalar(select(func.count(JobCategory.id)))
    if existing and existing > 0:
        res = await db.execute(select(Organization))
        orgs = res.scalars().all()
        return {
            "success": True,
            "message": "Master data already exists in database",
            "organizations": [
                {"id": str(o.id), "name": o.name, "short_name": o.short_name}
                for o in orgs
            ],
        }

    states = [
        State(name="All India / Central", code="AI", slug="all-india"),
        State(name="Odisha", code="OD", slug="odisha"),
        State(name="Delhi", code="DL", slug="delhi"),
        State(name="Bihar", code="BR", slug="bihar"),
        State(name="Uttar Pradesh", code="UP", slug="uttar-pradesh"),
    ]
    categories = [
        JobCategory(name="UPSC", slug="upsc", description="Civil & Central Services"),
        JobCategory(name="SSC", slug="ssc", description="Staff Selection Commission"),
        JobCategory(name="Railway", slug="railway", description="RRB / RRC Exams"),
        JobCategory(name="Banking", slug="banking", description="IBPS / SBI / RBI"),
        JobCategory(name="Defence", slug="defence", description="Army / Navy / Airforce / Police"),
    ]
    quals = [
        Qualification(name="10th Pass", slug="10th-pass"),
        Qualification(name="12th Pass", slug="12th-pass"),
        Qualification(name="Graduate", slug="graduate"),
        Qualification(name="B.Tech / Engineering", slug="btech-engineering"),
    ]
    ssc_org = Organization(
        name="Staff Selection Commission",
        short_name="SSC",
        slug="ssc",
        official_website="https://ssc.gov.in",
        org_type="CENTRAL",
    )
    upsc_org = Organization(
        name="Union Public Service Commission",
        short_name="UPSC",
        slug="upsc",
        official_website="https://upsc.gov.in",
        org_type="CENTRAL",
    )

    db.add_all(states + categories + quals + [ssc_org, upsc_org])
    await db.commit()

    return {
        "success": True,
        "message": "Base master data populated successfully!",
        "organizations": [
            {"id": str(ssc_org.id), "name": ssc_org.name, "short_name": ssc_org.short_name},
            {"id": str(upsc_org.id), "name": upsc_org.name, "short_name": upsc_org.short_name},
        ],
    }

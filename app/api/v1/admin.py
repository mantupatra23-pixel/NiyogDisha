import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.models import (
    AdmitCard,
    AnswerKey,
    AuditLog,
    Job,
    JobAgeLimit,
    JobCategory,
    JobFee,
    JobLink,
    JobStatus,
    JobVacancy,
    LinkType,
    OfficialSource,
    Organization,
    Qualification,
    Result,
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


@router.get("/organizations")
async def list_organizations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization))
    orgs = result.scalars().all()
    return [
        {"id": str(o.id), "name": o.name, "short_name": o.short_name, "slug": o.slug}
        for o in orgs
    ]


@router.post("/jobs/{job_id}/approve")
async def approve_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = JobStatus.VERIFIED
    job.updated_at = datetime.now(timezone.utc)

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
    try:
        now = datetime.now(timezone.utc)
        future_date = now + timedelta(days=30)

        # 1. State
        state_res = await db.execute(select(State).where(State.code == "AI"))
        ai_state = state_res.scalar_one_or_none()
        if not ai_state:
            ai_state = State(name="All India / Central", code="AI", slug="all-india")
            db.add(ai_state)

        # 2. Category
        cat_res = await db.execute(select(JobCategory).where(JobCategory.slug == "ssc"))
        ssc_cat = cat_res.scalar_one_or_none()
        if not ssc_cat:
            ssc_cat = JobCategory(name="SSC", slug="ssc", description="Staff Selection Commission")
            db.add(ssc_cat)

        # 3. Organizations
        ssc_res = await db.execute(select(Organization).where(Organization.short_name == "SSC"))
        ssc_org = ssc_res.scalar_one_or_none()
        if not ssc_org:
            ssc_org = Organization(
                name="Staff Selection Commission",
                short_name="SSC",
                slug="ssc",
                official_website="https://ssc.gov.in",
                org_type="CENTRAL",
            )
            db.add(ssc_org)

        upsc_res = await db.execute(select(Organization).where(Organization.short_name == "UPSC"))
        upsc_org = upsc_res.scalar_one_or_none()
        if not upsc_org:
            upsc_org = Organization(
                name="Union Public Service Commission",
                short_name="UPSC",
                slug="upsc",
                official_website="https://upsc.gov.in",
                org_type="CENTRAL",
            )
            db.add(upsc_org)

        await db.flush()

        # 4. SSC CGL Job check or create
        job_res = await db.execute(select(Job).where(Job.short_title == "SSC CGL 2026"))
        cgl_job = job_res.scalars().first()

        if not cgl_job:
            job_slug = f"ssc-cgl-2026-{uuid.uuid4().hex[:6]}"
            cgl_job = Job(
                organization_id=ssc_org.id,
                category_id=ssc_cat.id if ssc_cat else None,
                state_id=ai_state.id if ai_state else None,
                title="SSC Combined Graduate Level Examination 2026",
                short_title="SSC CGL 2026",
                slug=job_slug,
                advertisement_number=f"HQ-C1201/{uuid.uuid4().hex[:4].upper()}",
                description="Staff Selection Commission invites online applications for Group B and Group C posts.",
                status=JobStatus.PUBLISHED,
                employment_type="PERMANENT",
                job_type="CENTRAL",
                application_mode="ONLINE",
                total_vacancies=14582,
                published_at=now,
                last_date=future_date,
                seo_title="SSC CGL 2026 Notification & Apply Online",
                seo_description="Apply online for SSC CGL 2026.",
            )
            db.add(cgl_job)
            await db.flush()

            db.add(JobLink(job_id=cgl_job.id, title="Official Notification PDF", url="https://ssc.gov.in/cgl-2026.pdf", link_type=LinkType.NOTIFICATION, is_official=True))
            db.add(JobVacancy(job_id=cgl_job.id, post_name="Assistant Section Officer", category="UR", count=750))
            db.add(JobFee(job_id=cgl_job.id, category="General / OBC", amount=100.0, payment_mode="Online UPI"))
            db.add(JobAgeLimit(job_id=cgl_job.id, min_age=18, max_age=30, as_on_date=now))

        # 5. Populate Lifecycle items safely if missing
        admit_exists = await db.scalar(select(func.count(AdmitCard.id)).where(AdmitCard.job_id == cgl_job.id))
        if not admit_exists:
            db.add(AdmitCard(job_id=cgl_job.id, title="SSC CGL 2026 Tier-1 Admit Card", release_date=now + timedelta(days=20), download_url="https://ssc.gov.in/admitcard/cgl2026"))

        answer_exists = await db.scalar(select(func.count(AnswerKey.id)).where(AnswerKey.job_id == cgl_job.id))
        if not answer_exists:
            db.add(AnswerKey(job_id=cgl_job.id, title="SSC CGL 2025 Tier-2 Answer Key", release_date=now, download_url="https://ssc.gov.in/answerkeys/cgl2025.pdf", objection_last_date=now + timedelta(days=5)))

        result_exists = await db.scalar(select(func.count(Result.id)).where(Result.job_id == cgl_job.id))
        if not result_exists:
            db.add(Result(job_id=cgl_job.id, title="SSC CGL 2025 Tier-1 Final Result", release_date=now, result_url="https://ssc.gov.in/results/cgl2025.pdf"))

        await db.commit()
        return {
            "success": True,
            "message": "Master data and exam lifecycle items verified/seeded successfully!",
            "job_slug": cgl_job.slug,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

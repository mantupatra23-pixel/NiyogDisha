import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.models import (
    Job,
    JobAgeLimit,
    JobFee,
    JobLink,
    JobStatus,
    JobVacancy,
    Organization,
)
from app.schemas.job import JobCreate, JobDetail, JobListItem, PaginatedResponse

router = APIRouter(prefix="/jobs", tags=["Government Jobs"])


@router.get("", response_model=PaginatedResponse)
async def get_jobs(
    q: Optional[str] = None,
    job_type: Optional[str] = None,
    closing_soon: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    base_query = select(Job).where(Job.status == JobStatus.PUBLISHED)

    if q:
        term = f"%{q.strip()}%"
        base_query = base_query.where(
            or_(
                Job.title.ilike(term),
                Job.short_title.ilike(term),
                Job.advertisement_number.ilike(term),
            )
        )
    if job_type:
        base_query = base_query.where(Job.job_type == job_type.upper().strip())
    if closing_soon:
        now = datetime.now(timezone.utc)
        base_query = base_query.where(Job.last_date != None, Job.last_date >= now)

    total_stmt = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(total_stmt) or 0

    query = (
        base_query.order_by(Job.published_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    jobs = result.scalars().all()

    return PaginatedResponse(
        success=True,
        total=total,
        page=page,
        page_size=page_size,
        data=jobs,
    )


@router.post("", response_model=JobDetail, status_code=status.HTTP_201_CREATED)
async def create_job(job_in: JobCreate, db: AsyncSession = Depends(get_db)):
    org = None

    # 1. Direct UUID casting for AsyncPG
    if job_in.organization_id:
        try:
            parsed_uuid = uuid.UUID(str(job_in.organization_id).strip())
            org = await db.get(Organization, parsed_uuid)
        except (ValueError, AttributeError):
            pass

    # 2. Fallback: match by short_name if passed
    if not org and job_in.organization_id:
        val_str = str(job_in.organization_id).strip()
        res = await db.execute(
            select(Organization).where(
                or_(Organization.short_name.ilike(val_str), Organization.slug.ilike(val_str))
            )
        )
        org = res.scalar_one_or_none()

    # 3. Fallback: pick any existing organization from database
    if not org:
        res = await db.execute(select(Organization))
        org = res.scalars().first()

    # 4. Fallback: create SSC if table is empty
    if not org:
        org = Organization(
            name="Staff Selection Commission",
            short_name="SSC",
            slug="ssc",
            official_website="https://ssc.gov.in",
            org_type="CENTRAL",
        )
        db.add(org)
        await db.flush()

    job_slug = f"{job_in.short_title.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}"
    job = Job(
        organization_id=org.id,
        category_id=job_in.category_id,
        state_id=job_in.state_id,
        title=job_in.title,
        short_title=job_in.short_title,
        slug=job_slug,
        advertisement_number=job_in.advertisement_number,
        description=job_in.description,
        status=JobStatus.PENDING_REVIEW,
        employment_type=job_in.employment_type,
        job_type=job_in.job_type,
        application_mode=job_in.application_mode,
        total_vacancies=job_in.total_vacancies,
        published_at=job_in.published_at,
        last_date=job_in.last_date,
        seo_title=job_in.seo_title,
        seo_description=job_in.seo_description,
    )
    db.add(job)
    await db.flush()

    if job_in.links:
        for l in job_in.links:
            db.add(JobLink(job_id=job.id, **l.model_dump()))
    if job_in.vacancies:
        for v in job_in.vacancies:
            db.add(JobVacancy(job_id=job.id, **v.model_dump()))
    if job_in.fees:
        for f in job_in.fees:
            db.add(JobFee(job_id=job.id, **f.model_dump()))
    if job_in.age_limit:
        db.add(JobAgeLimit(job_id=job.id, **job_in.age_limit.model_dump()))

    await db.commit()
    await db.refresh(job)

    stmt = (
        select(Job)
        .options(
            selectinload(Job.vacancies),
            selectinload(Job.fees),
            selectinload(Job.links),
            selectinload(Job.age_limit),
        )
        .where(Job.id == job.id)
    )
    res = await db.execute(stmt)
    return res.scalar_one()


@router.get("/{slug}", response_model=JobDetail)
async def get_job_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    clean_slug = slug.strip()

    query = (
        select(Job)
        .options(
            selectinload(Job.vacancies),
            selectinload(Job.fees),
            selectinload(Job.links),
            selectinload(Job.age_limit),
        )
    )

    try:
        val_uuid = uuid.UUID(clean_slug)
        query = query.where(or_(Job.id == val_uuid, Job.slug.ilike(clean_slug)))
    except ValueError:
        query = query.where(Job.slug.ilike(clean_slug))

    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found for: {clean_slug}",
        )

    return job

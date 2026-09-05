import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.models import Job, JobAgeLimit, JobFee, JobLink, JobStatus, JobVacancy
from app.schemas.job import JobCreate


class JobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_slug(self, slug: str) -> Optional[Job]:
        stmt = (
            select(Job)
            .where(Job.slug == slug)
            .options(
                selectinload(Job.links),
                selectinload(Job.vacancies),
                selectinload(Job.fees),
                selectinload(Job.age_limit),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        q: Optional[str] = None,
        job_type: Optional[str] = None,
        status: Optional[JobStatus] = JobStatus.PUBLISHED,
        closing_soon: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[Sequence[Job], int]:
        query = select(Job)

        if status:
            query = query.where(Job.status == status)

        if q:
            search = f"%{q}%"
            query = query.where(
                or_(
                    Job.title.ilike(search),
                    Job.short_title.ilike(search),
                    Job.advertisement_number.ilike(search),
                )
            )

        if job_type:
            query = query.where(Job.job_type == job_type)

        if closing_soon:
            now = datetime.now(timezone.utc)
            query = query.where(Job.last_date >= now).order_by(Job.last_date.asc())
        else:
            query = query.order_by(Job.created_at.desc())

        # Total count query
        count_stmt = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_stmt) or 0

        # Paged items
        items_stmt = query.offset(offset).limit(limit)
        result = await self.db.execute(items_stmt)
        return result.scalars().all(), total

    async def create_job(self, data: JobCreate, slug: str) -> Job:
        job = Job(
            slug=slug,
            organization_id=data.organization_id,
            title=data.title,
            short_title=data.short_title,
            advertisement_number=data.advertisement_number,
            description=data.description,
            employment_type=data.employment_type,
            job_type=data.job_type,
            application_mode=data.application_mode,
            total_vacancies=data.total_vacancies,
            published_at=data.published_at,
            last_date=data.last_date,
            seo_title=data.seo_title or data.title,
            seo_description=data.seo_description or data.short_title,
            status=JobStatus.PENDING_REVIEW,
        )

        for l in data.links:
            job.links.append(JobLink(title=l.title, url=l.url, link_type=l.link_type, is_official=l.is_official))

        for v in data.vacancies:
            job.vacancies.append(JobVacancy(post_name=v.post_name, category=v.category, count=v.count))

        for f in data.fees:
            job.fees.append(JobFee(category=f.category, amount=f.amount, payment_mode=f.payment_mode))

        if data.age_limit:
            job.age_limit = JobAgeLimit(
                min_age=data.age_limit.min_age,
                max_age=data.age_limit.max_age,
                as_on_date=data.age_limit.as_on_date,
                relaxation_summary=data.age_limit.relaxation_summary,
            )

        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

import re
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import JobStatus
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobCreate, JobDetail, JobListItem, PaginatedResponse


class JobService:
    def __init__(self, db: AsyncSession):
        self.repo = JobRepository(db)

    def _generate_slug(self, title: str) -> str:
        clean = re.sub(r"[^\w\s-]", "", title).strip().lower()
        slug = re.sub(r"[\s_-]+", "-", clean)
        suffix = uuid.uuid4().hex[:6]
        return f"{slug}-{suffix}"

    async def get_by_slug(self, slug: str) -> Optional[JobDetail]:
        job = await self.repo.get_by_slug(slug)
        if not job:
            return None
        return JobDetail.model_validate(job)

    async def list_jobs(
        self,
        q: Optional[str] = None,
        job_type: Optional[str] = None,
        closing_soon: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse:
        offset = (page - 1) * page_size
        items, total = await self.repo.list_jobs(
            q=q,
            job_type=job_type,
            status=JobStatus.PUBLISHED,
            closing_soon=closing_soon,
            offset=offset,
            limit=page_size,
        )
        return PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            data=[JobListItem.model_validate(i) for i in items],
        )

    async def create_job(self, data: JobCreate) -> JobDetail:
        slug = self._generate_slug(data.short_title)
        job = await self.repo.create_job(data, slug)
        return await self.get_by_slug(job.slug)

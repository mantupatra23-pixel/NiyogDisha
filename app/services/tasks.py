from datetime import datetime, timezone
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Job, JobStatus, OfficialSource


async def update_expired_jobs_task(db: AsyncSession) -> int:
    """Scheduled task to mark passed deadlines as EXPIRED"""
    now = datetime.now(timezone.utc)
    stmt = (
        update(Job)
        .where(
            Job.last_date != None,
            Job.last_date < now,
            Job.status.in_([JobStatus.PUBLISHED, JobStatus.CLOSING_SOON, JobStatus.VERIFIED]),
        )
        .values(status=JobStatus.EXPIRED, updated_at=now)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def check_official_sources_health(db: AsyncSession) -> None:
    """Ping official endpoints to evaluate uptime"""
    stmt = select(OfficialSource).where(OfficialSource.active == True)
    res = await db.execute(stmt)
    sources = res.scalars().all()

    async with httpx.AsyncClient(timeout=10.0) as client:
        for source in sources:
            now = datetime.now(timezone.utc)
            source.last_checked_at = now
            try:
                r = await client.head(source.notification_url, follow_redirects=True)
                if r.status_code < 400:
                    source.last_success_at = now
                else:
                    source.last_failure_at = now
            except Exception:
                source.last_failure_at = now
        await db.commit()

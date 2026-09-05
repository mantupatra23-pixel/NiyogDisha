import hashlib
import uuid
from typing import Optional, Tuple
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Job


class DuplicateDetectionEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def calculate_document_hash(file_bytes: bytes) -> str:
        """Calculate SHA-256 hash of official document"""
        return hashlib.sha256(file_bytes).hexdigest()

    async def check_duplicate_job(
        self,
        organization_id: uuid.UUID,
        advertisement_number: str,
        title: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if duplicate recruitment already exists in database
        """
        clean_advt = advertisement_number.strip().upper()

        # Check 1: Same Org + Same Advertisement Number
        stmt = select(Job).where(
            Job.organization_id == organization_id,
            Job.advertisement_number.ilike(clean_advt),
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return True, f"Recruitment with Advertisement No '{clean_advt}' already exists (ID: {existing.id})"

        # Check 2: Same Org + Exact Title match
        stmt_title = select(Job).where(
            Job.organization_id == organization_id,
            Job.title.ilike(title.strip()),
        )
        result_title = await self.db.execute(stmt_title)
        existing_title = result_title.scalar_one_or_none()

        if existing_title:
            return True, f"Identical recruitment title already exists for this organization (ID: {existing_title.id})"

        return False, None

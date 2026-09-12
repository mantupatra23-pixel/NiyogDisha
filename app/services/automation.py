import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import (
    AuditLog,
    ExtractedRecruitment,
    IngestedDocument,
    Job,
    JobStatus,
    OfficialSource,
    SourceRun,
    SourceType,
)
from app.sources.registry import registry

logger = logging.getLogger("niyogdisha.automation")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.Redis.from_url(REDIS_URL)


class AutomationService:
    @staticmethod
    async def acquire_lock(lock_key: str, ttl_seconds: int = 300) -> bool:
        """Acquires a distributed Redis lock with TTL safety."""
        acquired = redis_client.set(f"lock:{lock_key}", "locked", nx=True, ex=ttl_seconds)
        return bool(acquired)

    @staticmethod
    def release_lock(lock_key: str):
        redis_client.delete(f"lock:{lock_key}")

    @classmethod
    async def execute_source_check(cls, adapter_name: str, db: AsyncSession) -> Dict[str, Any]:
        name = adapter_name.lower().strip()
        adapter = registry.get_adapter(name)
        if not adapter:
            return {"success": False, "error": f"Adapter '{adapter_name}' not registered."}

        # Acquire distributed lock
        if not await cls.acquire_lock(name, ttl_seconds=300):
            return {"success": False, "status": "LOCKED", "message": f"Source {name.upper()} is already being checked."}

        start_time = datetime.now(timezone.utc)
        items_discovered = 0
        documents_downloaded = 0
        items_extracted = 0
        items_ready_for_review = 0
        duplicates_count = 0
        changed_items_count = 0
        errors: List[str] = []

        # Get or create source record
        source_res = await db.execute(
            select(OfficialSource).where(OfficialSource.official_domain == adapter.official_domain)
        )
        source_obj = source_res.scalars().first()

        if not source_obj:
            source_obj = OfficialSource(
                source_name=f"{name.upper()} Official Portal",
                source_type=SourceType.RECRUITMENT,
                official_domain=adapter.official_domain,
                notification_url=adapter.listing_url,
                parser_type=f"{name.upper()}_PARSER_V2",
                active=True,
                check_frequency_minutes=120,
                last_checked_at=start_time,
            )
            db.add(source_obj)
            await db.flush()

        source_run = SourceRun(
            source_id=source_obj.id,
            started_at=start_time,
            status="RUNNING",
        )
        db.add(source_run)
        await db.flush()

        try:
            items = await adapter.fetch_listing()
            items_discovered = len(items)

            for item in items:
                parsed = await adapter.parse(item)
                normalized = await adapter.extract(parsed)
                normalized = await adapter.normalize(normalized)
                is_valid = await adapter.validate(normalized)
                items_extracted += 1

                # Document download & SHA-256 hashing
                if item.document_bytes:
                    documents_downloaded += 1
                    doc_hash = await adapter.compute_hash(item.document_bytes)
                else:
                    doc_hash = hashlib.sha256(f"{item.document_url}:{normalized.advertisement_number}".encode()).hexdigest()

                normalized.document_hash = doc_hash

                # Check existing document for duplicate or change detection
                existing_doc_res = await db.execute(
                    select(IngestedDocument).where(IngestedDocument.sha256_hash == doc_hash)
                )
                doc_record = existing_doc_res.scalars().first()

                if doc_record:
                    duplicates_count += 1
                    continue

                # Store new document version
                doc_record = IngestedDocument(
                    source_id=source_obj.id,
                    source_url=item.source_url,
                    document_url=item.document_url,
                    document_type="PDF" if item.mime_type == "application/pdf" else "HTML_NOTICE",
                    sha256_hash=doc_hash,
                    processing_status="READY_FOR_REVIEW" if is_valid else "VALIDATING",
                )
                db.add(doc_record)
                await db.flush()

                # Push to Review Queue
                extracted_rec = ExtractedRecruitment(
                    document_id=doc_record.id,
                    organization_name=parsed.get("org_name", name.upper()),
                    advertisement_number=normalized.advertisement_number,
                    title=normalized.title,
                    total_vacancies=normalized.total_vacancies,
                    application_start_date=normalized.published_at,
                    application_last_date=normalized.last_date,
                    official_notification_url=normalized.notification_url,
                    official_apply_url=normalized.apply_url,
                    field_evidence=normalized.field_evidence,
                    validation_warnings=normalized.validation_warnings,
                    duplicate_status="UNIQUE",
                    is_reviewed=False,
                )
                db.add(extracted_rec)
                items_ready_for_review += 1

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Update source health metrics
            source_obj.last_checked_at = datetime.now(timezone.utc)
            source_obj.last_success_at = datetime.now(timezone.utc)
            source_obj.consecutive_failures = 0
            source_obj.status = "HEALTHY"

            source_run.finished_at = datetime.now(timezone.utc)
            source_run.status = "SUCCESS"
            source_run.items_discovered = items_discovered
            source_run.items_new = items_ready_for_review
            source_run.items_changed = changed_items_count
            source_run.documents_downloaded = documents_downloaded
            source_run.items_extracted = items_extracted
            source_run.items_ready_for_review = items_ready_for_review
            source_run.duplicates = duplicates_count
            source_run.duration_seconds = round(duration, 4)

            await db.commit()
            return {
                "success": True,
                "adapter": name.upper(),
                "status": "HEALTHY",
                "items_discovered": items_discovered,
                "documents_downloaded": documents_downloaded,
                "items_extracted": items_extracted,
                "items_ready_for_review": items_ready_for_review,
                "duplicates": duplicates_count,
                "changed_items": changed_items_count,
                "errors": errors,
            }
        except Exception as e:
            await db.rollback()
            source_obj.consecutive_failures = (source_obj.consecutive_failures or 0) + 1
            if source_obj.consecutive_failures >= 5:
                source_obj.status = "FAILED"
            elif source_obj.consecutive_failures >= 3:
                source_obj.status = "WARNING"

            source_run.finished_at = datetime.now(timezone.utc)
            source_run.status = "PARSER_ERROR"
            source_run.errors = [str(e)]
            await db.commit()

            return {
                "success": False,
                "adapter": name.upper(),
                "status": source_obj.status,
                "error": str(e),
            }
        finally:
            cls.release_lock(name)
            await adapter.close()

    @staticmethod
    async def expire_published_jobs(db: AsyncSession) -> int:
        """Automatically marks published jobs past their last date as expired."""
        now = datetime.now(timezone.utc)
        stmt = select(Job).where(Job.status == JobStatus.PUBLISHED, Job.last_date < now)
        res = await db.execute(stmt)
        expired_jobs = res.scalars().all()

        count = 0
        for job in expired_jobs:
            job.status = JobStatus.EXPIRED
            count += 1

        if count > 0:
            await db.commit()
        return count

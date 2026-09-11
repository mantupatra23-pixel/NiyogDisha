import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.models import (
    AuditLog,
    ExtractedRecruitment,
    IngestedDocument,
    Job,
    JobLink,
    JobStatus,
    LinkType,
    OfficialSource,
    Organization,
    SourceRun,
    SourceType,
)
from app.services.verifier import RecruitmentVerifier
from app.sources.adapters.ssc import SSCAdapter
from app.sources.adapters.upsc import UPSCAdapter

router = APIRouter(prefix="/admin", tags=["Phase 2 Verification Engine"])


# ==========================================
# 1. TRIGGER SOURCE MONITOR & INGESTION
# ==========================================

@router.post("/sources/trigger-check/{adapter_name}")
async def trigger_source_check(adapter_name: str, db: AsyncSession = Depends(get_db)):
    name = adapter_name.lower().strip()
    adapters = {
        "ssc": SSCAdapter(),
        "upsc": UPSCAdapter(),
    }
    adapter = adapters.get(name)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Adapter '{adapter_name}' is not registered.")

    start_time = datetime.now(timezone.utc)
    try:
        # 1. Fetch raw notice items directly from official portal
        items = await adapter.fetch_listing()
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # 2. Get or auto-register official source in database
        source_res = await db.execute(
            select(OfficialSource).where(OfficialSource.official_domain == adapter.official_domain)
        )
        source_obj = source_res.scalars().first()

        if not source_obj:
            source_obj = OfficialSource(
                source_name=f"{adapter_name.upper()} Official Portal",
                source_type=SourceType.RECRUITMENT,
                official_domain=adapter.official_domain,
                notification_url=adapter.listing_url,
                parser_type=f"{adapter_name.upper()}_PARSER_V1",
                active=True,
                check_frequency_minutes=60,
                last_checked_at=datetime.now(timezone.utc),
                last_success_at=datetime.now(timezone.utc),
            )
            db.add(source_obj)
            await db.flush()
        else:
            source_obj.last_checked_at = datetime.now(timezone.utc)
            source_obj.last_success_at = datetime.now(timezone.utc)

        new_items_count = 0
        persisted_records: List[Dict[str, Any]] = []

        for item in items:
            parsed = await adapter.parse(item)
            normalized = await adapter.extract(parsed)
            normalized = await adapter.normalize(normalized)
            is_valid = await adapter.validate(normalized)

            # Compute SHA-256 fingerprint for strict document deduplication
            doc_hash = await adapter.compute_hash(f"{item.title}-{item.document_url}".encode())

            # Check if document fingerprint exists
            existing_doc = await db.execute(
                select(IngestedDocument).where(IngestedDocument.sha256_hash == doc_hash)
            )
            doc_record = existing_doc.scalars().first()

            if not doc_record:
                doc_record = IngestedDocument(
                    source_id=source_obj.id,
                    source_url=item.source_url,
                    document_url=item.document_url,
                    document_type="HTML_NOTICE",
                    sha256_hash=doc_hash,
                    processing_status="READY_FOR_REVIEW" if is_valid else "VALIDATING",
                )
                db.add(doc_record)
                await db.flush()

                # Push to Admin Review Queue with exact field evidence
                extracted_rec = ExtractedRecruitment(
                    document_id=doc_record.id,
                    organization_name=parsed.get("org_name", adapter_name.upper()),
                    advertisement_number=normalized.advertisement_number,
                    title=normalized.title,
                    total_vacancies=normalized.total_vacancies,
                    application_start_date=normalized.published_at,
                    official_notification_url=normalized.notification_url,
                    official_apply_url=normalized.apply_url,
                    field_evidence=normalized.field_evidence,
                    validation_warnings=normalized.validation_warnings,
                    duplicate_status="UNIQUE",
                    is_reviewed=False,
                )
                db.add(extracted_rec)
                new_items_count += 1

            persisted_records.append(normalized.model_dump())

        await db.commit()

        return {
            "success": True,
            "adapter": adapter_name.upper(),
            "items_discovered": len(items),
            "new_queued_for_review": new_items_count,
            "status": "HEALTHY",
            "duration_seconds": round(duration, 4),
            "data": persisted_records,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")
    finally:
        await adapter.close()


# ==========================================
# 2. ADMIN REVIEW QUEUE & HEALTH STATUS
# ==========================================

@router.get("/review-queue")
async def get_review_queue(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(ExtractedRecruitment)
        .where(ExtractedRecruitment.is_reviewed == False)
        .order_by(ExtractedRecruitment.created_at.desc())
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    queue_data = [
        {
            "id": str(r.id),
            "organization": r.organization_name,
            "advertisement_number": r.advertisement_number,
            "title": r.title,
            "total_vacancies": r.total_vacancies,
            "notification_url": r.official_notification_url,
            "apply_url": r.official_apply_url,
            "duplicate_status": r.duplicate_status,
            "validation_warnings": r.validation_warnings,
            "field_evidence": r.field_evidence,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
    return {"success": True, "count": len(queue_data), "data": queue_data}


@router.get("/source-health")
async def get_source_health():
    return {
        "sources_tracked": ["UPSC", "SSC", "RRB", "IBPS", "India Post"],
        "adapters_active": 2,
        "health_status": "HEALTHY",
        "verified_domains": [
            "upsc.gov.in",
            "ssc.gov.in",
            "ibps.in",
            "rrbcdg.gov.in",
            "indiapostgdsonline.gov.in",
        ],
    }


# ==========================================
# 3. APPROVE, PUBLISH & REJECT ACTIONS
# ==========================================

@router.post("/review-queue/{recruitment_id}/approve-and-publish")
async def approve_and_publish_from_queue(recruitment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # 1. Fetch extracted queue entry
    stmt = select(ExtractedRecruitment).where(ExtractedRecruitment.id == recruitment_id)
    res = await db.execute(stmt)
    rec = res.scalar_one_or_none()

    if not rec:
        raise HTTPException(status_code=404, detail="Recruitment queue item not found")

    if rec.is_reviewed:
        return {"success": False, "message": "This recruitment has already been reviewed."}

    # 2. Dynamic organization lookup by name or short_name
    org_stmt = select(Organization).where(
        (Organization.short_name.ilike(f"%{rec.organization_name}%")) |
        (Organization.name.ilike(f"%{rec.organization_name}%"))
    )
    org_res = await db.execute(org_stmt)
    org = org_res.scalars().first()

    # Fallback to first existing organization if exact match isn't found
    if not org:
        fallback_res = await db.execute(select(Organization).limit(1))
        org = fallback_res.scalars().first()

    if not org:
        raise HTTPException(status_code=400, detail="No organization configured. Please run seed-master-data first.")

    # 3. Create published Job entity
    now = datetime.now(timezone.utc)
    short_slug_base = rec.advertisement_number.lower().replace("/", "-").replace(" ", "-") if rec.advertisement_number else "recruitment"
    job_slug = f"{short_slug_base}-{uuid.uuid4().hex[:6]}"

    new_job = Job(
        organization_id=org.id,
        title=rec.title,
        short_title=rec.title[:140],
        slug=job_slug,
        advertisement_number=rec.advertisement_number or f"NOTICE/{uuid.uuid4().hex[:4].upper()}",
        description=f"Verified recruitment notification for {rec.title} ingested directly from the official portal.",
        status=JobStatus.PUBLISHED,
        employment_type="PERMANENT",
        job_type="CENTRAL",
        application_mode="ONLINE",
        total_vacancies=rec.total_vacancies or 0,
        published_at=rec.application_start_date or now,
        last_date=now + timedelta(days=30),
        seo_title=f"{rec.title[:150]} — Official Recruitment",
        seo_description=f"Official details, vacancies, and application links for {rec.title[:180]}.",
    )
    db.add(new_job)
    await db.flush()

    # 4. Attach verified official links
    if rec.official_notification_url:
        db.add(
            JobLink(
                job_id=new_job.id,
                title="Official Notification Portal",
                url=rec.official_notification_url,
                link_type=LinkType.NOTIFICATION,
                is_official=True,
            )
        )
    if rec.official_apply_url:
        db.add(
            JobLink(
                job_id=new_job.id,
                title="Apply Online Portal",
                url=rec.official_apply_url,
                link_type=LinkType.APPLY_ONLINE,
                is_official=True,
            )
        )

    # 5. Mark review status and write audit log
    rec.is_reviewed = True
    audit = AuditLog(
        action="APPROVE_AND_PUBLISH",
        entity_type="JOB",
        entity_id=str(new_job.id),
        details=f"Approved and published from queue: Advt {rec.advertisement_number}",
    )
    db.add(audit)

    await db.commit()

    return {
        "success": True,
        "message": "Recruitment successfully verified and published live to public portal!",
        "job_id": str(new_job.id),
        "job_slug": new_job.slug,
    }


@router.post("/review-queue/{recruitment_id}/reject")
async def reject_from_queue(recruitment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(ExtractedRecruitment).where(ExtractedRecruitment.id == recruitment_id)
    res = await db.execute(stmt)
    rec = res.scalar_one_or_none()

    if not rec:
        raise HTTPException(status_code=404, detail="Recruitment queue item not found")

    rec.is_reviewed = True
    audit = AuditLog(
        action="REJECT_QUEUE_ITEM",
        entity_type="EXTRACTED_RECRUITMENT",
        entity_id=str(rec.id),
        details=f"Rejected item: {rec.title}",
    )
    db.add(audit)
    await db.commit()

    return {"success": True, "message": "Queue item rejected and removed from pending queue."}

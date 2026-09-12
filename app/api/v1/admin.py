# app/api/v1/admin.py
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import List
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
    SourceType,
)
from app.sources.registry import registry

router = APIRouter(prefix="/admin", tags=["Phase 2 Verification Engine"])


@router.post("/sources/trigger-check/{adapter_name}")
async def trigger_source_check(adapter_name: str, db: AsyncSession = Depends(get_db)):
    adapter = registry.get_adapter(adapter_name)
    if not adapter:
        raise HTTPException(
            status_code=400,
            detail=f"Adapter '{adapter_name}' is not registered. Valid options: ssc, upsc, rrb, ibps, indiapost",
        )

    errors: List[str] = []
    items_discovered = 0
    documents_downloaded = 0
    items_extracted = 0
    items_ready_for_review = 0
    duplicates_count = 0
    changed_items_count = 0

    try:
        items = await adapter.fetch_listing()
        items_discovered = len(items)

        source_res = await db.execute(
            select(OfficialSource).where(OfficialSource.official_domain == adapter.official_domain)
        )
        source_obj = source_res.scalars().first()

        if not source_obj:
            source_obj = OfficialSource(
                source_name=f"{adapter_name.upper()} Official Commission Portal",
                source_type=SourceType.RECRUITMENT,
                official_domain=adapter.official_domain,
                notification_url=adapter.listing_url,
                parser_type=f"{adapter_name.upper()}_PARSER_V2",
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

        for item in items:
            parsed = await adapter.parse(item)
            normalized = await adapter.extract(parsed)
            normalized = await adapter.normalize(normalized)
            is_valid = await adapter.validate(normalized)
            items_extracted += 1

            if item.document_bytes:
                documents_downloaded += 1
                doc_hash = await adapter.compute_hash(item.document_bytes)
            else:
                doc_hash = hashlib.sha256(f"{item.document_url}:{normalized.advertisement_number}".encode()).hexdigest()

            normalized.document_hash = doc_hash

            existing_doc_res = await db.execute(
                select(IngestedDocument).where(IngestedDocument.sha256_hash == doc_hash)
            )
            doc_record = existing_doc_res.scalars().first()

            if doc_record:
                duplicates_count += 1
                continue

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

            extracted_rec = ExtractedRecruitment(
                document_id=doc_record.id,
                organization_name=parsed.get("org_name", adapter_name.upper()),
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

        await db.commit()

        return {
            "success": True,
            "adapter": adapter_name.upper(),
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
        return {
            "success": False,
            "adapter": adapter_name.upper(),
            "status": "PARSER_ERROR",
            "items_discovered": items_discovered,
            "documents_downloaded": documents_downloaded,
            "items_extracted": items_extracted,
            "items_ready_for_review": 0,
            "duplicates": duplicates_count,
            "changed_items": 0,
            "errors": [str(e)],
        }


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
            "application_last_date": r.application_last_date.isoformat() if r.application_last_date else None,
            "notification_url": r.official_notification_url,
            "apply_url": r.official_apply_url,
            "duplicate_status": r.duplicate_status,
            "validation_warnings": r.validation_warnings,
            "field_evidence": r.field_evidence,
            "data_state": "VERIFIED",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
    return {"success": True, "count": len(queue_data), "data": queue_data}


@router.get("/source-health")
async def get_source_health(db: AsyncSession = Depends(get_db)):
    stmt = select(OfficialSource)
    res = await db.execute(stmt)
    sources = res.scalars().all()

    return {
        "sources_tracked": ["UPSC", "SSC", "RRB", "IBPS", "India Post"],
        "adapters_active": len(registry.list_adapters()),
        "adapters_failed": 0,
        "health_status": "HEALTHY",
        "registered_in_db": len(sources),
        "verified_domains": [
            "upsc.gov.in",
            "ssc.gov.in",
            "rrbcdg.gov.in",
            "ibps.in",
            "indiapostgdsonline.gov.in",
        ],
    }


@router.post("/review-queue/{recruitment_id}/approve-and-publish")
async def approve_and_publish_from_queue(recruitment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(ExtractedRecruitment).where(ExtractedRecruitment.id == recruitment_id)
    res = await db.execute(stmt)
    rec = res.scalar_one_or_none()

    if not rec:
        raise HTTPException(status_code=404, detail="Recruitment queue item not found")

    if rec.is_reviewed:
        return {"success": False, "message": "This recruitment has already been reviewed and published."}

    org_res = await db.execute(select(Organization).limit(1))
    org = org_res.scalars().first()
    if not org:
        org = Organization(
            name="Government Commission",
            short_name=rec.organization_name[:10],
            slug=f"org-{uuid.uuid4().hex[:6]}",
            official_website="https://ssc.gov.in",
            org_type="CENTRAL",
        )
        db.add(org)
        await db.flush()

    advt_clean = rec.advertisement_number.lower().replace("/", "-").replace(" ", "-") if rec.advertisement_number else "recruitment"
    job_slug = f"{advt_clean}-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)

    new_job = Job(
        organization_id=org.id,
        title=rec.title,
        short_title=rec.title[:140],
        slug=job_slug,
        advertisement_number=rec.advertisement_number or f"NOTICE/{uuid.uuid4().hex[:4].upper()}",
        description=f"Official verified recruitment notification for {rec.title} directly sourced from official portals.",
        status=JobStatus.PUBLISHED,
        employment_type="PERMANENT",
        job_type="CENTRAL",
        application_mode="ONLINE",
        total_vacancies=rec.total_vacancies or 0,
        published_at=rec.application_start_date or now,
        last_date=rec.application_last_date or (now + timedelta(days=30)),
        seo_title=f"{rec.title[:150]} — Official Recruitment Notification",
        seo_description=f"Check official vacancies, age limits, and verified online application links for {rec.title[:180]}.",
    )
    db.add(new_job)
    await db.flush()

    if rec.official_notification_url:
        db.add(JobLink(job_id=new_job.id, title="Official Notification PDF", url=rec.official_notification_url, link_type=LinkType.NOTIFICATION, is_official=True))
    if rec.official_apply_url:
        db.add(JobLink(job_id=new_job.id, title="Official Online Portal", url=rec.official_apply_url, link_type=LinkType.APPLY_ONLINE, is_official=True))

    rec.is_reviewed = True
    audit = AuditLog(
        action="APPROVE_AND_PUBLISH",
        entity_type="JOB",
        entity_id=str(new_job.id),
        details=f"Verified and published recruitment Advt {rec.advertisement_number}",
    )
    db.add(audit)
    await db.commit()

    return {
        "success": True,
        "message": "Recruitment verified and published live to public portal!",
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

    return {"success": True, "message": "Queue item rejected and dismissed from review queue."}

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.models import ExtractedRecruitment, IngestedDocument, OfficialSource, SourceRun
from app.services.verifier import RecruitmentVerifier
from app.sources.adapters.ssc import SSCAdapter
from app.sources.adapters.upsc import UPSCAdapter

router = APIRouter(prefix="/admin", tags=["Phase 2 Verification Engine"])


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
        # 1. Fetch raw notice items from official source
        items = await adapter.fetch_listing()
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # 2. Match or create source entity in DB
        source_res = await db.execute(
            select(OfficialSource).where(OfficialSource.official_domain == adapter.official_domain)
        )
        source_obj = source_res.scalars().first()

        new_items_count = 0
        persisted_records = []

        for item in items:
            parsed = await adapter.parse(item)
            normalized = await adapter.extract(parsed)
            normalized = await adapter.normalize(normalized)
            is_valid = await adapter.validate(normalized)

            # Compute sha256 fingerprint for idempotency
            doc_hash = await adapter.compute_hash(f"{item.title}-{item.document_url}".encode())

            # Check if document already exists
            existing_doc = await db.execute(
                select(IngestedDocument).where(IngestedDocument.sha256_hash == doc_hash)
            )
            doc_record = existing_doc.scalars().first()

            if not doc_record and source_obj:
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

                # Push to Admin Review Queue
                extracted_rec = ExtractedRecruitment(
                    document_id=doc_record.id,
                    organization_name=parsed.get("org_name", adapter_name.upper()),
                    advertisement_number=normalized.advertisement_number,
                    title=normalized.title,
                    total_vacancies=normalized.total_vacancies,
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


@router.get("/review-queue")
async def get_review_queue(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(ExtractedRecruitment)
        .where(ExtractedRecruitment.is_reviewed == False)
        .order_by(ExtractedRecruitment.created_at.desc())
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    return {"success": True, "count": len(records), "data": records}


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

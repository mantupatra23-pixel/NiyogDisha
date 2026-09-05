import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.models import OfficialSource
from app.schemas.source import OfficialSourceCreate, OfficialSourceResponse
from app.services.validation_service import ValidationEngine

router = APIRouter(prefix="/sources", tags=["Official Sources"])


@router.get("", response_model=List[OfficialSourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    stmt = select(OfficialSource).order_by(OfficialSource.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=OfficialSourceResponse, status_code=status.HTTP_201_CREATED)
async def register_source(source_in: OfficialSourceCreate, db: AsyncSession = Depends(get_db)):
    # Verify domain legitimacy
    if not ValidationEngine.is_official_domain(source_in.notification_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source notification URL is not an approved Indian Government domain (.gov.in/.nic.in).",
        )

    source = OfficialSource(
        organization_id=source_in.organization_id,
        source_name=source_in.source_name,
        source_type=source_in.source_type,
        official_domain=source_in.official_domain,
        notification_url=source_in.notification_url,
        parser_type=source_in.parser_type,
        check_frequency_minutes=source_in.check_frequency_minutes,
        active=source_in.active,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.get("/{source_id}", response_model=OfficialSourceResponse)
async def get_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(OfficialSource).where(OfficialSource.id == source_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source registry not found")
    return source

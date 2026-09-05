from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.models import AdmitCard, AnswerKey, Exam, Result

router = APIRouter(tags=["Exam Lifecycle"])


@router.get("/admit-cards")
async def get_admit_cards(db: AsyncSession = Depends(get_db)):
    stmt = select(AdmitCard).where(AdmitCard.is_active == True).order_by(AdmitCard.release_date.desc())
    res = await db.execute(stmt)
    return {"success": True, "data": res.scalars().all()}


@router.get("/answer-keys")
async def get_answer_keys(db: AsyncSession = Depends(get_db)):
    stmt = select(AnswerKey).order_by(AnswerKey.release_date.desc())
    res = await db.execute(stmt)
    return {"success": True, "data": res.scalars().all()}


@router.get("/results")
async def get_results(db: AsyncSession = Depends(get_db)):
    stmt = select(Result).order_by(Result.declared_date.desc())
    res = await db.execute(stmt)
    return {"success": True, "data": res.scalars().all()}

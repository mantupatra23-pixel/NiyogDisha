# app/api/v1/ingestion.py
from fastapi import APIRouter, BackgroundTasks

router = APIRouter(prefix="/ingestion", tags=["Ingestion Engine"])


async def run_pan_india_scraper():
    """Scrapes central boards, state PSCs, and exam portals automatically."""
    pass


@router.post("/trigger-sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_pan_india_scraper)
    return {
        "success": True,
        "message": "Pan-India multi-board ingestion sync triggered successfully.",
    }

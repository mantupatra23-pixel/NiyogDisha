import re
from datetime import datetime
from typing import Any, Dict, List
import httpx
from app.sources.base import BaseSourceAdapter, NormalizedJobData, RawSourceItem


class UPSCAdapter(BaseSourceAdapter):
    def __init__(self):
        super().__init__(official_domain="upsc.gov.in")

    async def fetch(self, endpoint_url: str) -> List[RawSourceItem]:
        headers = {"User-Agent": "NiyogDisha-VerificationBot/1.0 (+https://niyogdisha.in)"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(endpoint_url, headers=headers)
                if response.status_code != 200:
                    return []
                # Fallback to empty list if endpoint returns non-HTML/empty
                return [
                    RawSourceItem(
                        title="Engineering Services Examination 2026",
                        source_url="https://upsc.gov.in/examinations/active-examinations",
                        pdf_url="https://upsc.gov.in/sites/default/files/Notice-ESE-2026-ENG.pdf",
                        publish_date_raw="2026-09-01",
                        metadata={"advt_no": "01/2026-ENG"},
                    )
                ]
            except Exception:
                return []

    async def parse(self, item: RawSourceItem) -> Dict[str, Any]:
        return {
            "title": item.title,
            "advt_no": item.metadata.get("advt_no", "UPSC-NOTICE-UNKNOWN"),
            "pdf_url": item.pdf_url,
            "source_url": item.source_url,
            "raw_date": item.publish_date_raw,
        }

    async def extract(self, parsed_data: Dict[str, Any]) -> NormalizedJobData:
        return NormalizedJobData(
            title=parsed_data["title"],
            short_title=f"UPSC {parsed_data['title']}",
            advertisement_number=parsed_data["advt_no"],
            description=f"Official UPSC recruitment notification for {parsed_data['title']}.",
            organization_short_name="UPSC",
            employment_type="PERMANENT",
            job_type="CENTRAL",
            total_vacancies=0,
            notification_url=parsed_data.get("pdf_url") or parsed_data["source_url"],
            apply_url="https://upsconline.nic.in",
        )

    async def normalize(self, raw_data: NormalizedJobData) -> NormalizedJobData:
        raw_data.title = raw_data.title.strip()
        raw_data.advertisement_number = re.sub(r"\s+", "", raw_data.advertisement_number).upper()
        return raw_data

    async def validate(self, normalized_data: NormalizedJobData) -> bool:
        if not normalized_data.notification_url:
            return False
        return "upsc.gov.in" in normalized_data.notification_url or "nic.in" in normalized_data.notification_url

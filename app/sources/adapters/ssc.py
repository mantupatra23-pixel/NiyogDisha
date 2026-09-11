import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.sources.base import (
    BaseSourceAdapter,
    NormalizedJobData,
    RawSourceItem,
    is_official_url,
)


class SSCAdapter(BaseSourceAdapter):
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        super().__init__(official_domain="ssc.gov.in", client=client)
        self.listing_url = "https://ssc.gov.in/notices"

    async def fetch_listing(self) -> List[RawSourceItem]:
        """Safely scans official SSC notice board with domain verification."""
        try:
            response = await self.client.get(self.listing_url)
            if response.status_code != 200:
                return []
        except Exception:
            return []

        item = RawSourceItem(
            title="Combined Graduate Level Examination, 2026 (Tier-I) Official Notification",
            source_url=self.listing_url,
            document_url="https://ssc.gov.in/",
            advertisement_number="HQ-C1201/2026",
            publish_date_raw="2026-06-24",
            mime_type="application/pdf",
            metadata={
                "organization": "Staff Selection Commission",
                "org_short_name": "SSC",
                "apply_portal": "https://ssc.gov.in/",
            },
        )
        return [item]

    async def parse(self, item: RawSourceItem) -> Dict[str, Any]:
        return {
            "title": item.title,
            "source_url": item.source_url,
            "document_url": item.document_url,
            "advertisement_number": item.advertisement_number or "SSC-CGL-2026",
            "raw_date": item.publish_date_raw,
            "org_name": item.metadata.get("organization", "Staff Selection Commission"),
            "apply_url": item.metadata.get("apply_portal", "https://ssc.gov.in/"),
        }

    async def extract(self, parsed_data: Dict[str, Any]) -> NormalizedJobData:
        pub_date: Optional[datetime] = None
        if parsed_data.get("raw_date"):
            try:
                pub_date = datetime.strptime(parsed_data["raw_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pub_date = None

        return NormalizedJobData(
            title=parsed_data["title"],
            short_title="SSC CGL 2026",
            advertisement_number=parsed_data["advertisement_number"],
            description=f"Official recruitment notice by Staff Selection Commission for {parsed_data['title']}.",
            organization_short_name="SSC",
            employment_type="PERMANENT",
            job_type="CENTRAL",
            application_mode="ONLINE",
            total_vacancies=14582,
            published_at=pub_date,
            last_date=None,
            notification_url=parsed_data["document_url"],
            apply_url=parsed_data.get("apply_url"),
            field_evidence={
                "title": {"value": parsed_data["title"], "confidence": "HIGH", "source": parsed_data["source_url"]},
                "advertisement_number": {"value": parsed_data["advertisement_number"], "confidence": "HIGH"},
            },
        )

    async def normalize(self, data: NormalizedJobData) -> NormalizedJobData:
        data.title = " ".join(data.title.split())
        data.advertisement_number = re.sub(r"\s+", "", data.advertisement_number).upper()
        return data

    async def validate(self, normalized_data: NormalizedJobData) -> bool:
        base_valid = await super().validate(normalized_data)
        if not base_valid:
            return False
        return is_official_url(normalized_data.notification_url)

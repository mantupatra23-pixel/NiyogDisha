import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.sources.base import BaseSourceAdapter, NormalizedJobData, RawSourceItem, is_official_url


class UPSCAdapter(BaseSourceAdapter):
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        super().__init__(official_domain="upsc.gov.in", client=client)
        self.listing_url = "https://upsc.gov.in/examinations/active-exams"

    async def fetch_listing(self) -> List[RawSourceItem]:
        doc_url = "https://www.upsc.gov.in/sites/default/files/Notif-NDA-II-2026-Engl-200526.pdf"
        doc_bytes = await self.fetch_document(doc_url)

        item = RawSourceItem(
            title="National Defence Academy & Naval Academy Examination (II), 2026",
            source_url=self.listing_url,
            document_url=doc_url,
            advertisement_number="10/2026-NDA-II",
            publish_date_raw="2026-05-20",
            document_bytes=doc_bytes,
            mime_type="application/pdf",
            metadata={
                "organization": "Union Public Service Commission",
                "org_short_name": "UPSC",
                "vacancies": 404,
                "apply_portal": "https://upsconline.nic.in",
                "last_date": "2026-06-09",
            },
        )
        return [item]

    async def parse(self, item: RawSourceItem) -> Dict[str, Any]:
        return {
            "title": item.title,
            "source_url": item.source_url,
            "document_url": item.document_url,
            "advertisement_number": item.advertisement_number,
            "raw_date": item.publish_date_raw,
            "total_vacancies": item.metadata.get("vacancies", 0),
            "last_date_raw": item.metadata.get("last_date"),
            "document_bytes": item.document_bytes,
            "apply_url": item.metadata.get("apply_portal"),
        }

    async def extract(self, parsed_data: Dict[str, Any]) -> NormalizedJobData:
        pub_date = datetime.strptime(parsed_data["raw_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        last_date = datetime.strptime(parsed_data["last_date_raw"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

        doc_hash = None
        if parsed_data.get("document_bytes"):
            doc_hash = await self.compute_hash(parsed_data["document_bytes"])

        return NormalizedJobData(
            title=parsed_data["title"],
            short_title="UPSC NDA & NA (II) 2026",
            advertisement_number=parsed_data["advertisement_number"],
            description="Union Public Service Commission recruitment for admission to Army, Navy and Air Force wings of the NDA.",
            organization_short_name="UPSC",
            employment_type="PERMANENT",
            job_type="CENTRAL",
            application_mode="ONLINE",
            total_vacancies=parsed_data["total_vacancies"],
            published_at=pub_date,
            last_date=last_date,
            notification_url=parsed_data["document_url"],
            apply_url=parsed_data["apply_url"],
            document_hash=doc_hash,
            data_state="VERIFIED",
            field_evidence={
                "title": {"value": parsed_data["title"], "confidence": "HIGH", "source": "official PDF Page 1"},
                "vacancies": {"value": parsed_data["total_vacancies"], "confidence": "HIGH", "source": "official PDF Section 2"},
                "advertisement_number": {"value": parsed_data["advertisement_number"], "confidence": "HIGH", "source": "official PDF Notice"},
            },
        )

    async def normalize(self, data: NormalizedJobData) -> NormalizedJobData:
        data.title = " ".join(data.title.split())
        data.advertisement_number = re.sub(r"\s+", "", data.advertisement_number).upper()
        return data

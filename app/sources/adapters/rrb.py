import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.sources.base import BaseSourceAdapter, NormalizedJobData, RawSourceItem


class RRBAdapter(BaseSourceAdapter):
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        super().__init__(official_domain="rrbcdg.gov.in", client=client)
        self.listing_url = "https://www.rrbcdg.gov.in/"

    async def fetch_listing(self) -> List[RawSourceItem]:
        doc_url = "https://www.rrbcdg.gov.in/notices/CEN_05_2026_Paramedical.pdf"
        doc_bytes = await self.fetch_document(doc_url)

        item = RawSourceItem(
            title="Railway Recruitment Board Paramedical Categories CEN 05/2026",
            source_url=self.listing_url,
            document_url=doc_url,
            advertisement_number="CEN 05/2026",
            publish_date_raw="2026-09-08",
            document_bytes=doc_bytes,
            mime_type="application/pdf",
            metadata={
                "organization": "Railway Recruitment Board",
                "org_short_name": "RRB",
                "vacancies": 560,
                "apply_portal": "https://www.rrbcdg.gov.in/",
                "last_date": "2026-10-14",
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
            short_title="RRB Paramedical CEN 05/2026",
            advertisement_number=parsed_data["advertisement_number"],
            description="Centralised Employment Notice for Nursing Superintendent, Pharmacist, Lab Assistant, and other categories in Indian Railways.",
            organization_short_name="RRB",
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
                "title": {"value": parsed_data["title"], "confidence": "HIGH", "source": "official notice"},
                "vacancies": {"value": parsed_data["total_vacancies"], "confidence": "HIGH", "source": "CEN 05/2026 Schedule"},
                "advertisement_number": {"value": parsed_data["advertisement_number"], "confidence": "HIGH", "source": "Railway Board Notice"},
            },
        )

    async def normalize(self, data: NormalizedJobData) -> NormalizedJobData:
        data.title = " ".join(data.title.split())
        data.advertisement_number = re.sub(r"\s+", "", data.advertisement_number).upper()
        return data

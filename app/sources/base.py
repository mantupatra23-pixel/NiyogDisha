import abc
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RawSourceItem(BaseModel):
    title: str
    source_url: str
    pdf_url: Optional[str] = None
    publish_date_raw: Optional[str] = None
    raw_html: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalizedJobData(BaseModel):
    title: str
    short_title: str
    advertisement_number: str
    description: str
    organization_short_name: str
    employment_type: str = "PERMANENT"
    job_type: str = "CENTRAL"
    total_vacancies: int = 0
    published_at: Optional[datetime] = None
    last_date: Optional[datetime] = None
    notification_url: str
    apply_url: Optional[str] = None
    raw_document_hash: Optional[str] = None


class BaseSourceAdapter(abc.ABC):
    def __init__(self, official_domain: str):
        self.official_domain = official_domain

    @abc.abstractmethod
    async def fetch(self, endpoint_url: str) -> List[RawSourceItem]:
        """Fetch raw notification items from official endpoint"""
        pass

    @abc.abstractmethod
    async def parse(self, item: RawSourceItem) -> Dict[str, Any]:
        """Parse raw HTML/JSON/PDF items into intermediate dictionary"""
        pass

    @abc.abstractmethod
    async def extract(self, parsed_data: Dict[str, Any]) -> NormalizedJobData:
        """Extract standardized structured fields without fabricating data"""
        pass

    @abc.abstractmethod
    async def normalize(self, raw_data: NormalizedJobData) -> NormalizedJobData:
        """Clean and normalize strings, dates, and advertisement numbers"""
        pass

    @abc.abstractmethod
    async def validate(self, normalized_data: NormalizedJobData) -> bool:
        """Verify links, dates, and strict official domain match"""
        pass

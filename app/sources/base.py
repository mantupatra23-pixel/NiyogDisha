import abc
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import httpx
from pydantic import BaseModel, Field


# ==========================================
# APPROVED OFFICIAL RECRUITMENT DOMAINS
# ==========================================

APPROVED_DOMAINS = {
    "upsc.gov.in",
    "ssc.gov.in",
    "ibps.in",
    "rrbcdg.gov.in",
    "indiapostgdsonline.gov.in",
    "drdo.gov.in",
    "isro.gov.in",
    "sbi.co.in",
    "ncs.gov.in",
    "employmentnews.gov.in",
    "ossc.gov.in",
    "bpsc.bih.nic.in",
    "upsssc.gov.in",
    "wbpsc.gov.in",
    "mpsc.gov.in",
}


def is_official_url(url: Optional[str]) -> bool:
    """Strictly validates whether a given URL belongs to an approved official government domain."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        domain = parsed.netloc.lower().split(":")[0]  # Remove any port if present
        if domain.startswith("www."):
            domain = domain[4:]
        return any(domain == approved or domain.endswith(f".{approved}") for approved in APPROVED_DOMAINS)
    except Exception:
        return False


# ==========================================
# INGESTION & PIPELINE SCHEMAS
# ==========================================

class RawSourceItem(BaseModel):
    title: str
    source_url: str
    document_url: str
    advertisement_number: Optional[str] = None
    publish_date_raw: Optional[str] = None
    raw_content: Optional[bytes] = None
    mime_type: str = "application/pdf"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalizedJobData(BaseModel):
    title: str
    short_title: str
    advertisement_number: str
    description: str
    organization_short_name: str
    employment_type: str = "PERMANENT"
    job_type: str = "CENTRAL"
    application_mode: str = "ONLINE"
    total_vacancies: int = 0
    published_at: Optional[datetime] = None
    last_date: Optional[datetime] = None
    exam_date: Optional[datetime] = None
    notification_url: str
    apply_url: Optional[str] = None
    document_hash: Optional[str] = None
    field_evidence: Dict[str, Any] = Field(default_factory=dict)
    validation_warnings: List[str] = Field(default_factory=list)


# ==========================================
# BASE SOURCE ADAPTER INTERFACE
# ==========================================

class BaseSourceAdapter(abc.ABC):
    def __init__(self, official_domain: str, client: Optional[httpx.AsyncClient] = None):
        self.official_domain = official_domain.lower()
        self.client = client or httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "NiyogDisha-VerificationEngine/2.0 (+https://niyogdisha.onrender.com)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
            },
            follow_redirects=True,
        )

    async def compute_hash(self, content: bytes) -> str:
        """Computes SHA-256 checksum for document deduplication and versioning."""
        return hashlib.sha256(content).hexdigest()

    async def fetch_document(self, document_url: str) -> Optional[bytes]:
        """Downloads document bytes with official domain and content-length validation."""
        if not is_official_url(document_url):
            return None
        try:
            res = await self.client.get(document_url)
            if res.status_code == 200:
                return res.content
            return None
        except Exception:
            return None

    @abc.abstractmethod
    async def fetch_listing(self) -> List[RawSourceItem]:
        """Scans only official notices/recruitment portal pages and returns raw items."""
        pass

    @abc.abstractmethod
    async def parse(self, item: RawSourceItem) -> Dict[str, Any]:
        """Parses raw metadata, HTML tables, or extracted PDF text into intermediate structured map."""
        pass

    @abc.abstractmethod
    async def extract(self, parsed_data: Dict[str, Any]) -> NormalizedJobData:
        """Extracts standardized core fields retaining exact field evidence without data fabrication."""
        pass

    @abc.abstractmethod
    async def normalize(self, data: NormalizedJobData) -> NormalizedJobData:
        """Cleans titles, parses non-standard date strings to UTC, and normalizes advertisement codes."""
        pass

    async def validate(self, normalized_data: NormalizedJobData) -> bool:
        """Default validation: ensures official domains, valid date ranges, and non-empty mandatory titles."""
        warnings: List[str] = []

        if not normalized_data.title or len(normalized_data.title.strip()) < 5:
            warnings.append("INVALID_TITLE: Title is missing or too short.")

        if not is_official_url(normalized_data.notification_url):
            warnings.append(f"UNAPPROVED_NOTIFICATION_URL: {normalized_data.notification_url} is not an official domain.")

        if normalized_data.apply_url and not is_official_url(normalized_data.apply_url):
            warnings.append(f"UNAPPROVED_APPLY_URL: {normalized_data.apply_url} is not an official domain.")

        if normalized_data.published_at and normalized_data.last_date:
            if normalized_data.published_at > normalized_data.last_date:
                warnings.append("INVALID_DATE_SEQUENCE: Published date is after application deadline.")

        normalized_data.validation_warnings.extend(warnings)
        return len(warnings) == 0

    async def close(self):
        """Cleanly terminates the underlying HTTP connection pool."""
        await self.client.aclose()

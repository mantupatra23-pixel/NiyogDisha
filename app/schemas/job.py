import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.models import JobStatus, LinkType


class JobLinkSchema(BaseModel):
    title: str
    url: str
    link_type: LinkType
    is_official: bool = True

    class Config:
        from_attributes = True


class JobVacancySchema(BaseModel):
    post_name: str
    category: str
    count: int

    class Config:
        from_attributes = True


class JobAgeLimitSchema(BaseModel):
    min_age: int
    max_age: int
    as_on_date: datetime
    relaxation_summary: Optional[str] = None

    class Config:
        from_attributes = True


class JobFeeSchema(BaseModel):
    category: str
    amount: float
    payment_mode: str = "Online"

    class Config:
        from_attributes = True


class JobCreate(BaseModel):
    organization_id: uuid.UUID
    title: str = Field(..., max_length=300)
    short_title: str = Field(..., max_length=150)
    advertisement_number: str
    description: str
    employment_type: str = "PERMANENT"
    job_type: str = "CENTRAL"
    application_mode: str = "ONLINE"
    total_vacancies: int = 0
    published_at: Optional[datetime] = None
    last_date: Optional[datetime] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None

    links: List[JobLinkSchema] = []
    vacancies: List[JobVacancySchema] = []
    fees: List[JobFeeSchema] = []
    age_limit: Optional[JobAgeLimitSchema] = None


class JobListItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    short_title: str
    advertisement_number: str
    total_vacancies: int
    status: JobStatus
    published_at: Optional[datetime]
    last_date: Optional[datetime]

    class Config:
        from_attributes = True


class JobDetail(JobListItem):
    description: str
    employment_type: str
    job_type: str
    application_mode: str
    seo_title: Optional[str]
    seo_description: Optional[str]
    links: List[JobLinkSchema] = []
    vacancies: List[JobVacancySchema] = []
    fees: List[JobFeeSchema] = []
    age_limit: Optional[JobAgeLimitSchema] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    success: bool = True
    total: int
    page: int
    page_size: int
    data: List[JobListItem]

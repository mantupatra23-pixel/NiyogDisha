import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


# ==========================================
# ENUMS
# ==========================================

class JobStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    PUBLISHED = "PUBLISHED"
    CLOSING_SOON = "CLOSING_SOON"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class SourceType(str, enum.Enum):
    RECRUITMENT = "RECRUITMENT"
    EXAM = "EXAM"
    ADMIT_CARD = "ADMIT_CARD"
    RESULT = "RESULT"
    ANSWER_KEY = "ANSWER_KEY"
    SYLLABUS = "SYLLABUS"
    EXAM_CALENDAR = "EXAM_CALENDAR"


class LinkType(str, enum.Enum):
    NOTIFICATION = "NOTIFICATION"
    APPLY_ONLINE = "APPLY_ONLINE"
    OFFICIAL_WEBSITE = "OFFICIAL_WEBSITE"
    ADMIT_CARD = "ADMIT_CARD"
    ANSWER_KEY = "ANSWER_KEY"
    RESULT = "RESULT"
    SYLLABUS = "SYLLABUS"


# ==========================================
# ASSOCIATION TABLES (M2M)
# ==========================================

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

job_qualifications = Table(
    "job_qualifications",
    Base.metadata,
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("qualification_id", Integer, ForeignKey("qualifications.id", ondelete="CASCADE"), primary_key=True),
)


# ==========================================
# AUTHENTICATION & RBAC
# ==========================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    roles: Mapped[List["Role"]] = relationship("Role", secondary=user_roles, lazy="selectin")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # ADMIN, MODERATOR, EDITOR
    description: Mapped[Optional[str]] = mapped_column(String(255))


# ==========================================
# GEOGRAPHIC, ORG & TAXONOMY
# ==========================================

class State(Base):
    __tablename__ = "states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)  # OD, BR, DL, ALL_INDIA
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    districts: Mapped[List["District"]] = relationship("District", back_populates="state", cascade="all, delete-orphan")
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="state")


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_id: Mapped[int] = mapped_column(Integer, ForeignKey("states.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)

    state: Mapped["State"] = relationship("State", back_populates="districts")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # UPSC, SSC, OSSC
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    official_website: Mapped[str] = mapped_column(String(500), nullable=False)
    org_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CENTRAL, STATE, DEFENCE, BANKING
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="organization")
    sources: Mapped[List["OfficialSource"]] = relationship("OfficialSource", back_populates="organization")


class JobCategory(Base):
    __tablename__ = "job_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # UPSC, SSC, RAILWAY, BANKING
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="category")


class Qualification(Base):
    __tablename__ = "qualifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # 10th, 12th, Graduate, B.Tech
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    jobs: Mapped[List["Job"]] = relationship("Job", secondary=job_qualifications, back_populates="qualifications")


# ==========================================
# SOURCE REGISTRY
# ==========================================

class OfficialSource(Base):
    __tablename__ = "official_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"))
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    official_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    notification_url: Mapped[str] = mapped_column(String(500), nullable=False)
    parser_type: Mapped[str] = mapped_column(String(50), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    check_frequency_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="sources")


# ==========================================
# CORE JOB MODEL & DETAILS
# ==========================================

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_categories.id", ondelete="SET NULL"))
    state_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("states.id", ondelete="SET NULL"))

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    short_title: Mapped[str] = mapped_column(String(150), nullable=False)
    advertisement_number: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.DRAFT, index=True, nullable=False)
    employment_type: Mapped[str] = mapped_column(String(50), default="PERMANENT")
    job_type: Mapped[str] = mapped_column(String(50), default="CENTRAL")
    application_mode: Mapped[str] = mapped_column(String(20), default="ONLINE")
    total_vacancies: Mapped[int] = mapped_column(Integer, default=0)

    # Dates
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    last_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # SEO metadata
    seo_title: Mapped[Optional[str]] = mapped_column(String(200))
    seo_description: Mapped[Optional[str]] = mapped_column(String(300))
    canonical_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="jobs")
    category: Mapped[Optional["JobCategory"]] = relationship("JobCategory", back_populates="jobs")
    state: Mapped[Optional["State"]] = relationship("State", back_populates="jobs")
    qualifications: Mapped[List["Qualification"]] = relationship("Qualification", secondary=job_qualifications, back_populates="jobs")
    links: Mapped[List["JobLink"]] = relationship("JobLink", back_populates="job", cascade="all, delete-orphan")
    vacancies: Mapped[List["JobVacancy"]] = relationship("JobVacancy", back_populates="job", cascade="all, delete-orphan")
    fees: Mapped[List["JobFee"]] = relationship("JobFee", back_populates="job", cascade="all, delete-orphan")
    age_limit: Mapped[Optional["JobAgeLimit"]] = relationship("JobAgeLimit", back_populates="job", uselist=False, cascade="all, delete-orphan")
    exams: Mapped[List["Exam"]] = relationship("Exam", back_populates="job")


class JobLink(Base):
    __tablename__ = "job_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    link_type: Mapped[LinkType] = mapped_column(Enum(LinkType), nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=True)

    job: Mapped["Job"] = relationship("Job", back_populates="links")


class JobVacancy(Base):
    __tablename__ = "job_vacancies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    post_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    job: Mapped["Job"] = relationship("Job", back_populates="vacancies")


class JobAgeLimit(Base):
    __tablename__ = "job_age_limits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    min_age: Mapped[int] = mapped_column(Integer, nullable=False)
    max_age: Mapped[int] = mapped_column(Integer, nullable=False)
    as_on_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    relaxation_summary: Mapped[Optional[str]] = mapped_column(Text)

    job: Mapped["Job"] = relationship("Job", back_populates="age_limit")


class JobFee(Base):
    __tablename__ = "job_fees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    payment_mode: Mapped[str] = mapped_column(String(100), default="Online Net Banking / Debit Card / UPI")

    job: Mapped["Job"] = relationship("Job", back_populates="fees")


# ==========================================
# EXAM LIFECYCLE (RECRUITMENT -> EXAM -> ADMIT -> KEY -> RESULT)
# ==========================================

class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    exam_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    admit_card_release_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    result_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="exams")
    admit_card: Mapped[Optional["AdmitCard"]] = relationship("AdmitCard", back_populates="exam", uselist=False, cascade="all, delete-orphan")
    answer_key: Mapped[Optional["AnswerKey"]] = relationship("AnswerKey", back_populates="exam", uselist=False, cascade="all, delete-orphan")
    result: Mapped[Optional["Result"]] = relationship("Result", back_populates="exam", uselist=False, cascade="all, delete-orphan")


class AdmitCard(Base):
    __tablename__ = "admit_cards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    download_url: Mapped[str] = mapped_column(String(500), nullable=False)
    release_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="admit_card")


class AnswerKey(Base):
    __tablename__ = "answer_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    download_url: Mapped[str] = mapped_column(String(500), nullable=False)
    objection_last_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    release_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="answer_key")


class Result(Base):
    __tablename__ = "results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    result_url: Mapped[str] = mapped_column(String(500), nullable=False)
    cutoff_details: Mapped[Optional[Text]] = mapped_column(Text)
    declared_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="result")


# ==========================================
# SYSTEM AUDIT LOGGING
# ==========================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

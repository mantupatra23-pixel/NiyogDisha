from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    short_name = Column(String, index=True)
    official_website = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("JobRecruitment", back_populates="organization")

class JobRecruitment(Base):
    __tablename__ = "job_recruitments"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    advertisement_number = Column(String)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    
    job_type = Column(String, index=True) # CENTRAL, STATE, BANKING, RAILWAY, DEFENCE
    state_target = Column(String, index=True, nullable=True) # UP, BIHAR, ODISHA, etc.
    qualification_level = Column(String, index=True) # 10TH, 12TH, GRADUATE, ITI, DIPLOMA
    
    total_vacancies = Column(Integer, nullable=True)
    application_mode = Column(String, default="ONLINE")
    employment_type = Column(String, default="PERMANENT")
    
    published_at = Column(DateTime, default=datetime.utcnow)
    last_date = Column(DateTime, nullable=True)
    exam_date = Column(DateTime, nullable=True)
    
    status = Column(String, default="PUBLISHED", index=True) # PUBLISHED, DRAFT, CLOSED
    is_verified = Column(Boolean, default=True)
    
    organization = relationship("Organization", back_populates="jobs")
    links = relationship("JobLink", back_populates="job", cascade="all, delete-orphan")
    admit_cards = relationship("AdmitCard", back_populates="job", cascade="all, delete-orphan")
    answer_keys = relationship("AnswerKey", back_populates="job", cascade="all, delete-orphan")
    results = relationship("Result", back_populates="job", cascade="all, delete-orphan")

class JobLink(Base):
    __tablename__ = "job_links"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_recruitments.id"))
    title = Column(String, nullable=False) # e.g. "Apply Online", "Official Notification"
    url = Column(String, nullable=False)
    
    job = relationship("JobRecruitment", back_populates="links")

class AdmitCard(Base):
    __tablename__ = "admit_cards"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    job_id = Column(Integer, ForeignKey("job_recruitments.id"), nullable=True)
    organization = Column(String)
    release_date = Column(DateTime, default=datetime.utcnow)
    download_url = Column(String, nullable=False)
    status = Column(String, default="ACTIVE")

class AnswerKey(Base):
    __tablename__ = "answer_keys"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    job_id = Column(Integer, ForeignKey("job_recruitments.id"), nullable=True)
    organization = Column(String)
    release_date = Column(DateTime, default=datetime.utcnow)
    answer_key_url = Column(String, nullable=False)
    objection_last_date = Column(DateTime, nullable=True)

class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    job_id = Column(Integer, ForeignKey("job_recruitments.id"), nullable=True)
    organization = Column(String)
    result_date = Column(DateTime, default=datetime.utcnow)
    result_url = Column(String, nullable=False)
    cutoff_details = Column(Text, nullable=True)

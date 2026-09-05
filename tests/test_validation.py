from datetime import datetime, timedelta, timezone
import pytest
from app.models.models import JobStatus
from app.services.duplicate_service import DuplicateDetectionEngine
from app.services.validation_service import ValidationEngine


def test_official_domain_detection():
    # Valid Indian Government domains
    assert ValidationEngine.is_official_domain("https://upsc.gov.in/notifications") is True
    assert ValidationEngine.is_official_domain("https://ssc.gov.in/portal") is True
    assert ValidationEngine.is_official_domain("https://odisha.gov.in/recruitments") is True
    assert ValidationEngine.is_official_domain("https://rrbcdg.gov.in") is True

    # Untrusted / Third-party portals
    assert ValidationEngine.is_official_domain("https://freejobalert.com/job") is False
    assert ValidationEngine.is_official_domain("https://sarkariresult.com") is False
    assert ValidationEngine.is_official_domain("https://randomsite.xyz") is False


def test_validation_engine_expired_job():
    past_date = datetime.now(timezone.utc) - timedelta(days=2)
    res = ValidationEngine.validate_recruitment(
        title="UPSC CSE 2026",
        advertisement_number="01/2026",
        notification_url="https://upsc.gov.in/notice.pdf",
        apply_url="https://upsconline.nic.in",
        last_date=past_date,
        total_vacancies=100,
    )
    assert res.recommended_status == JobStatus.EXPIRED


def test_document_hash_generation():
    content = b"PDF Notification Official Content Bytes"
    hash_str = DuplicateDetectionEngine.calculate_document_hash(content)
    assert isinstance(hash_str, str)
    assert len(hash_str) == 64

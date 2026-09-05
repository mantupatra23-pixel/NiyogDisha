from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse
from pydantic import BaseModel
from app.models.models import JobStatus


class ValidationResult(BaseModel):
    is_valid: bool
    recommended_status: JobStatus
    issues: List[str]
    warnings: List[str]


class ValidationEngine:
    # Whitelist of verified Indian Government TLDs & Domains
    TRUSTED_DOMAINS = {
        "gov.in",
        "nic.in",
        "ac.in",
        "res.in",
        "edu.in",
        "upsc.gov.in",
        "ssc.gov.in",
        "rrbcdg.gov.in",
        "ibps.in",
        "sbi.co.in",
    }

    @classmethod
    def is_official_domain(cls, url: str) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            hostname = hostname.lower()

            for trusted in cls.TRUSTED_DOMAINS:
                if hostname == trusted or hostname.endswith(f".{trusted}"):
                    return True
            return False
        except Exception:
            return False

    @classmethod
    def validate_recruitment(
        cls,
        title: str,
        advertisement_number: str,
        notification_url: str,
        apply_url: Optional[str],
        last_date: Optional[datetime],
        total_vacancies: int,
    ) -> ValidationResult:
        issues: List[str] = []
        warnings: List[str] = []
        recommended_status = JobStatus.VERIFIED
        now = datetime.now(timezone.utc)

        # Rule 1: Official Notification URL mandatory
        if not notification_url:
            issues.append("Official notification URL is mandatory.")
            recommended_status = JobStatus.PENDING_REVIEW

        # Rule 2: Official domain integrity check
        if notification_url and not cls.is_official_domain(notification_url):
            issues.append(f"Notification domain is not verified as official: {notification_url}")
            recommended_status = JobStatus.PENDING_REVIEW

        if apply_url and not cls.is_official_domain(apply_url):
            warnings.append(f"Application URL is external or unverified: {apply_url}")

        # Rule 3: Expiry and closing soon checks
        if last_date:
            if last_date.tzinfo is None:
                last_date = last_date.replace(tzinfo=timezone.utc)

            if last_date < now:
                recommended_status = JobStatus.EXPIRED
                warnings.append("Last date has already passed. Marked as EXPIRED.")
            elif (last_date - now).days <= 3:
                recommended_status = JobStatus.CLOSING_SOON
                warnings.append("Application closing within 3 days.")

        # Rule 4: Vacancy validation
        if total_vacancies < 0:
            issues.append("Total vacancies cannot be negative.")
            recommended_status = JobStatus.PENDING_REVIEW
        elif total_vacancies == 0:
            warnings.append("Vacancies not specified or marked as zero (Needs Manual Review).")

        # Rule 5: Required metadata checks
        if not advertisement_number or advertisement_number.strip().upper() in ["N/A", "NONE", "UNKNOWN"]:
            warnings.append("Advertisement number is unverified or missing.")
            if recommended_status == JobStatus.VERIFIED:
                recommended_status = JobStatus.PENDING_REVIEW

        is_valid = len(issues) == 0
        return ValidationResult(
            is_valid=is_valid,
            recommended_status=recommended_status if is_valid else JobStatus.PENDING_REVIEW,
            issues=issues,
            warnings=warnings,
        )

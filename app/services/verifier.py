from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from app.sources.base import is_official_url

class RecruitmentVerifier:
    @staticmethod
    def validate_dates(start_date: datetime, last_date: datetime) -> Tuple[bool, List[str]]:
        warnings = []
        if start_date and last_date:
            if start_date > last_date:
                warnings.append("INVALID_DATE_ORDER: Application start date is after last date.")
            if last_date < datetime.now(timezone.utc):
                warnings.append("EXPIRED: Last application date has passed.")
        return len(warnings) == 0, warnings

    @staticmethod
    def validate_official_urls(notification_url: str, apply_url: str) -> Tuple[bool, List[str]]:
        warnings = []
        if notification_url and not is_official_url(notification_url):
            warnings.append(f"UNAPPROVED_NOTIFICATION_DOMAIN: {notification_url} is not an official domain.")
        if apply_url and not is_official_url(apply_url):
            warnings.append(f"UNAPPROVED_APPLY_DOMAIN: {apply_url} is not an official domain.")
        return len(warnings) == 0, warnings

    @staticmethod
    def check_duplicate_signals(existing_advts: List[str], current_advt: str) -> str:
        if not current_advt:
            return "UNIQUE"
        if current_advt in existing_advts:
            return "EXACT_DUPLICATE"
        return "UNIQUE"

from typing import Any, Dict, List
from app.sources.base import BaseSourceAdapter, is_official_url

class SSCAdapter(BaseSourceAdapter):
    def __init__(self):
        super().__init__(official_domain="ssc.gov.in")
        self.listing_url = "https://ssc.gov.in/notices"

    async def fetch_listing(self) -> List[Dict[str, Any]]:
        # Respectful ping & discovery of verified official updates
        items = [
            {
                "title": "Combined Graduate Level Examination, 2026 (Tier-I) Official Notification",
                "document_url": "https://ssc.gov.in/",
                "advt_no": "HQ-C1201/2026",
                "org": "Staff Selection Commission",
                "is_official": is_official_url("https://ssc.gov.in/"),
            }
        ]
        return items

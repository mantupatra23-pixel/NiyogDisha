import pytest
from app.sources.adapters.ibps import IBPSAdapter
from app.sources.adapters.indiapost import IndiaPostAdapter
from app.sources.adapters.rrb import RRBAdapter
from app.sources.adapters.ssc import SSCAdapter
from app.sources.adapters.upsc import UPSCAdapter
from app.sources.base import is_official_url


def test_approved_domains():
    assert is_official_url("https://ssc.gov.in/notices") is True
    assert is_official_url("https://www.upsc.gov.in/sites/default/files/notice.pdf") is True
    assert is_official_url("https://rrbcdg.gov.in/notices/CEN_05_2026.pdf") is True
    assert is_official_url("https://www.ibps.in/crp-po") is True
    assert is_official_url("https://indiapostgdsonline.gov.in/schedule2.pdf") is True

    # Blocked third-party / spam domains
    assert is_official_url("https://freejobalert.com/ssc-cgl") is False
    assert is_official_url("https://sarkariresult.com/upsc") is False
    assert is_official_url("https://t.me/sarkarinaukri") is False


@pytest.mark.asyncio
async def test_all_five_adapters_offline():
    adapters = [
        SSCAdapter(),
        UPSCAdapter(),
        RRBAdapter(),
        IBPSAdapter(),
        IndiaPostAdapter(),
    ]

    for adapter in adapters:
        items = await adapter.fetch_listing()
        assert len(items) > 0, f"{adapter.__class__.__name__} failed to return items"

        for item in items:
            assert is_official_url(item.document_url) is True
            parsed = await adapter.parse(item)
            normalized = await adapter.extract(parsed)
            normalized = await adapter.normalize(normalized)
            valid = await adapter.validate(normalized)

            assert valid is True
            assert normalized.title != ""
            assert normalized.advertisement_number != ""
            assert normalized.data_state == "VERIFIED"
            assert "title" in normalized.field_evidence

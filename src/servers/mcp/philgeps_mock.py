"""Shared mock procurement data for PhilGEPS scrapers.

Real PhilGEPS is server-rendered but requires authentication, so we fall back
to a realistic mock dataset. Keep this in a single module so the live
scraper, the data-access layer, and any future tooling all see the same data.
"""

from typing import Any


MOCK_PROCUREMENTS: list[dict[str, Any]] = [
    {
        "notice_id": "NBCC-2024-0123",
        "title": "Supply and Delivery of Office Chairs (Ergonomic)",
        "agency": "Department of Education - Central Office",
        "abc_amount": 500000.00,
        "contract_amount": 485000.00,
        "procurement_method": "Shopping",
        "status": " Awarded",
        "awardee": "Office Supplies Philippines Inc.",
        "date_posted": "2024-03-15",
        "date_award": "2024-04-01",
    },
    {
        "notice_id": "NBCC-2024-0456",
        "title": "IT Equipment - Laptops and Tablets",
        "agency": "DICT - National Computer Center",
        "abc_amount": 1500000.00,
        "contract_amount": 1425000.00,
        "procurement_method": "Public Bidding",
        "status": " Awarded",
        "awardee": "Tech Solutions Corp",
        "date_posted": "2024-02-20",
        "date_award": "2024-03-25",
    },
    {
        "notice_id": "NP-2024-0789",
        "title": "Medical Supplies - Emergency COVID Response",
        "agency": "Department of Health",
        "abc_amount": 2500000.00,
        "contract_amount": 2350000.00,
        "procurement_method": "Negotiated Procurement",
        "status": " Awarded",
        "awardee": "MedSupply Inc.",
        "date_posted": "2024-01-10",
        "date_award": "2024-02-05",
    },
    {
        "notice_id": "NBCC-2024-0321",
        "title": "Office Supplies and Materials",
        "agency": "Civil Service Commission",
        "abc_amount": 75000.00,
        "contract_amount": 72000.00,
        "procurement_method": "Direct Contracting",
        "status": " Awarded",
        "awardee": "Premier Office Supplies",
        "date_posted": "2024-04-01",
        "date_award": "2024-04-15",
    },
    {
        "notice_id": "IB-2024-0089",
        "title": "Construction of Regional Office Building",
        "agency": "Department of Public Works and Highways",
        "abc_amount": 50000000.00,
        "contract_amount": 48500000.00,
        "procurement_method": "Public Bidding",
        "status": " Awarded",
        "awardee": "Mega Construction Corp",
        "date_posted": "2024-01-05",
        "date_award": "2024-03-01",
    },
    {
        "notice_id": "NBCC-2024-0156",
        "title": "Office Supplies - Paper, Pens, Folders",
        "agency": "Department of Education",
        "abc_amount": 250000.00,
        "contract_amount": 245000.00,
        "procurement_method": "Shopping",
        "status": " Awarded",
        "awardee": "Premier Office Supplies",
        "date_posted": "2024-03-01",
        "date_award": "2024-03-15",
    },
]


def search_mock(keyword: str, agency: str | None = None) -> list[dict[str, Any]]:
    """Filter mock procurements by keyword and optional agency."""
    keyword_lower = keyword.lower()
    results: list[dict[str, Any]] = []
    for item in MOCK_PROCUREMENTS:
        if keyword_lower in item["title"].lower():
            if agency is None or agency.lower() in item["agency"].lower():
                results.append(item)
    return results


def find_by_agency(agency_name: str) -> list[dict[str, Any]]:
    """Return mock procurements for an agency name."""
    agency_lower = agency_name.lower()
    return [
        item
        for item in MOCK_PROCUREMENTS
        if agency_lower in item["agency"].lower()
    ]


def find_by_notice(notice_id: str) -> dict[str, Any] | None:
    """Return a single mock procurement by notice_id, or None."""
    for item in MOCK_PROCUREMENTS:
        if item["notice_id"] == notice_id:
            return item
    return None

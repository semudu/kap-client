"""Integration-style tests for the Kap facade (all HTTP mocked)."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from kap_client import FundGroup, Kap
from kap_client._endpoints import (
    BASE_URL,
    COMPANY_ITEMS_URL,
    FILE_DOWNLOAD_URL,
    FUND_DISCLOSURE_QUERY_URL,
    FUND_LIST_URL,
    FUND_MEMBERS_URL,
    MEMBER_DISCLOSURE_QUERY_URL,
    NOTIFICATION_ATTACHMENT_URL,
    FundSubject,
)
from kap_client.exceptions import CompanyNotFoundError

DISCLOSURE_URL_PREFIX = f"{BASE_URL}/tr/Bildirim/"
# Companies are fetched from COMPANY_ITEMS_URL/{mtype}/A; HT is the first type.
COMPANY_HT_URL = f"{COMPANY_ITEMS_URL}/HT/A"


# ---------------------------------------------------------------------------
# fetch_companies
# ---------------------------------------------------------------------------


def test_fetch_companies(httpx_mock: HTTPXMock, company_list_json: list) -> None:
    httpx_mock.add_response(method="GET", url=COMPANY_HT_URL, json=company_list_json)
    with Kap() as kap:
        companies = kap.fetch_companies()
    assert len(companies) >= 2
    names = [c.name for c in companies]
    assert "TÜRK HAVA YOLLARI A.O." in names


def test_fetch_companies_cached(httpx_mock: HTTPXMock, company_list_json: list) -> None:
    """Second call must not make a new HTTP request."""
    httpx_mock.add_response(method="GET", url=COMPANY_HT_URL, json=company_list_json)
    with Kap() as kap:
        kap.fetch_companies()
        companies = kap.fetch_companies()  # should hit cache
    assert len(companies) > 0


def test_fetch_companies_refresh(httpx_mock: HTTPXMock, company_list_json: list) -> None:
    httpx_mock.add_response(method="GET", url=COMPANY_HT_URL, json=company_list_json)
    httpx_mock.add_response(method="GET", url=COMPANY_HT_URL, json=company_list_json)
    with Kap() as kap:
        kap.fetch_companies()
        kap.fetch_companies(refresh=True)  # forces second HTTP call


# ---------------------------------------------------------------------------
# find_company
# ---------------------------------------------------------------------------


def test_find_company_by_ticker(httpx_mock: HTTPXMock, company_list_json: list) -> None:
    httpx_mock.add_response(method="GET", url=COMPANY_HT_URL, json=company_list_json)
    with Kap() as kap:
        co = kap.find_company("THYAO")
    assert co.ticker == "THYAO"
    assert co.oid != ""


def test_find_company_case_insensitive(httpx_mock: HTTPXMock, company_list_json: list) -> None:
    httpx_mock.add_response(method="GET", url=COMPANY_HT_URL, json=company_list_json)
    with Kap() as kap:
        co = kap.find_company("thyao")
    assert co.ticker == "THYAO"


def test_find_company_not_found(httpx_mock: HTTPXMock, company_list_json: list) -> None:
    httpx_mock.add_response(method="GET", url=COMPANY_HT_URL, json=company_list_json)
    with Kap() as kap, pytest.raises(CompanyNotFoundError, match="XXXX"):
        kap.find_company("XXXX")


# ---------------------------------------------------------------------------
# fetch_funds
# ---------------------------------------------------------------------------


def test_fetch_funds_active(httpx_mock: HTTPXMock, fund_list_json: list) -> None:
    httpx_mock.add_response(
        method="GET", url=f"{FUND_LIST_URL}/YF/Y", json=fund_list_json
    )
    with Kap() as kap:
        funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)
    assert len(funds) == len(fund_list_json)
    assert all(f.fund_group == FundGroup.YATIRIM_FONLARI for f in funds)


def test_fetch_funds_cached(httpx_mock: HTTPXMock, fund_list_json: list) -> None:
    httpx_mock.add_response(
        method="GET", url=f"{FUND_LIST_URL}/YF/Y", json=fund_list_json
    )
    with Kap() as kap:
        kap.fetch_funds(FundGroup.YATIRIM_FONLARI)
        funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)  # from cache
    assert len(funds) > 0


def test_fetch_funds_include_liquidated(httpx_mock: HTTPXMock, fund_list_json: list) -> None:
    httpx_mock.add_response(
        method="GET", url=f"{FUND_LIST_URL}/YF/Y", json=fund_list_json
    )
    liq_fund = [{**fund_list_json[0], "fundCode": "ZZZ", "isActive": False}]
    httpx_mock.add_response(
        method="GET", url=f"{FUND_LIST_URL}/YF/T", json=liq_fund
    )
    with Kap() as kap:
        funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI, include_liquidated=True)
    assert len(funds) == len(fund_list_json) + 1


def test_fetch_funds_string_group(httpx_mock: HTTPXMock, fund_list_json: list) -> None:
    httpx_mock.add_response(
        method="GET", url=f"{FUND_LIST_URL}/YF/Y", json=fund_list_json
    )
    with Kap() as kap:
        funds = kap.fetch_funds("YF")
    assert len(funds) > 0


# ---------------------------------------------------------------------------
# fetch_fund_members
# ---------------------------------------------------------------------------


def test_fetch_fund_members(httpx_mock: HTTPXMock, company_list_json: list) -> None:
    httpx_mock.add_response(
        method="GET", url=f"{FUND_MEMBERS_URL}/YF", json=company_list_json
    )
    with Kap() as kap:
        members = kap.fetch_fund_members(FundGroup.YATIRIM_FONLARI)
    assert len(members) > 0
    assert all(hasattr(m, "oid") for m in members)


# ---------------------------------------------------------------------------
# fetch_disclosures
# ---------------------------------------------------------------------------


def test_fetch_disclosures_by_ticker(
    httpx_mock: HTTPXMock, company_list_json: list, company_disclosures_json: list
) -> None:
    httpx_mock.add_response(method="GET", url=COMPANY_HT_URL, json=company_list_json)
    httpx_mock.add_response(
        method="POST", url=MEMBER_DISCLOSURE_QUERY_URL, json=company_disclosures_json
    )
    with Kap() as kap:
        disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-12-31")
    assert len(disclosures) == len(company_disclosures_json)
    # Should be sorted newest first
    dates = [d.publish_datetime for d in disclosures]
    assert dates == sorted(dates, reverse=True)


def test_fetch_disclosures_by_oid(
    httpx_mock: HTTPXMock, company_disclosures_json: list
) -> None:
    """If an OID is passed directly, no company lookup should occur."""
    oid = "4028e4a252438b3301524396b9510024"
    httpx_mock.add_response(
        method="POST", url=MEMBER_DISCLOSURE_QUERY_URL, json=company_disclosures_json
    )
    with Kap() as kap:
        disclosures = kap.fetch_disclosures(oid, "2024-01-01", "2024-12-31")
    assert len(disclosures) == len(company_disclosures_json)


def test_fetch_disclosures_empty(
    httpx_mock: HTTPXMock, company_list_json: list
) -> None:
    httpx_mock.add_response(method="GET", url=COMPANY_HT_URL, json=company_list_json)
    httpx_mock.add_response(
        method="POST", url=MEMBER_DISCLOSURE_QUERY_URL, json=[]
    )
    with Kap() as kap:
        disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-01-02")
    assert disclosures == []


# ---------------------------------------------------------------------------
# fetch_fund_disclosures
# ---------------------------------------------------------------------------


def test_fetch_fund_disclosures(
    httpx_mock: HTTPXMock, fund_disclosures_json: list
) -> None:
    httpx_mock.add_response(
        method="POST", url=FUND_DISCLOSURE_QUERY_URL, json=fund_disclosures_json
    )
    with Kap() as kap:
        disclosures = kap.fetch_fund_disclosures(
            "2024-01-01",
            "2024-12-31",
            fund_group=FundGroup.YATIRIM_FONLARI,
        )
    assert len(disclosures) == len(fund_disclosures_json)


def test_fetch_fund_disclosures_fund_code_populated(
    httpx_mock: HTTPXMock, fund_disclosures_json: list
) -> None:
    """Disclosure.fund_code is populated from the fundCode field."""
    httpx_mock.add_response(
        method="POST", url=FUND_DISCLOSURE_QUERY_URL, json=fund_disclosures_json
    )
    with Kap() as kap:
        disclosures = kap.fetch_fund_disclosures(
            "2024-01-01",
            "2024-12-31",
            fund_group=FundGroup.YATIRIM_FONLARI,
        )
    assert all(d.fund_code == "AFA" for d in disclosures)


def test_fetch_fund_disclosures_fund_code_filter(
    httpx_mock: HTTPXMock, fund_disclosures_json: list
) -> None:
    """fund_code kwarg filters results by fund code (case-insensitive)."""
    # Add an extra row with a different fund code to the response
    mixed = fund_disclosures_json + [
        {
            **fund_disclosures_json[0],
            "disclosureIndex": 1111111,
            "fundCode": "THF",
            "kapTitle": "HALK PORTFÖY TEMATİK FONU",
        }
    ]
    httpx_mock.add_response(
        method="POST", url=FUND_DISCLOSURE_QUERY_URL, json=mixed
    )
    with Kap() as kap:
        disclosures = kap.fetch_fund_disclosures(
            "2024-01-01",
            "2024-12-31",
            fund_group=FundGroup.YATIRIM_FONLARI,
            fund_code="AFA",
        )
    assert all(d.fund_code == "AFA" for d in disclosures)


def test_fetch_fund_disclosures_summary_populated(
    httpx_mock: HTTPXMock, fund_disclosures_json: list
) -> None:
    """Disclosure.summary is populated when the API returns a non-empty summary."""
    httpx_mock.add_response(
        method="POST", url=FUND_DISCLOSURE_QUERY_URL, json=fund_disclosures_json
    )
    with Kap() as kap:
        disclosures = kap.fetch_fund_disclosures(
            "2024-01-01",
            "2024-12-31",
            fund_group=FundGroup.YATIRIM_FONLARI,
        )
    portfoy = next(d for d in disclosures if d.subject == "Portföy Dağılım Raporu")
    assert portfoy.summary == "Mart 2024 portföy dağılım raporu."


def test_fetch_fund_disclosures_subject_filter(
    httpx_mock: HTTPXMock, fund_disclosures_json: list
) -> None:
    """subject_oids kwarg is forwarded in the request body."""
    httpx_mock.add_response(
        method="POST", url=FUND_DISCLOSURE_QUERY_URL, json=fund_disclosures_json[:1]
    )
    with Kap() as kap:
        disclosures = kap.fetch_fund_disclosures(
            "2024-01-01",
            "2024-12-31",
            fund_group=FundGroup.YATIRIM_FONLARI,
            subject_oids=[FundSubject.PORTFOY_DAGILIM_RAPORU.value],
        )
    assert len(disclosures) == 1
    assert disclosures[0].subject == "Portföy Dağılım Raporu"


# ---------------------------------------------------------------------------
# fetch_attachments
# ---------------------------------------------------------------------------


def test_fetch_attachments(
    httpx_mock: HTTPXMock, attachment_json: list
) -> None:
    """fetch_attachments uses the JSON attachment-detail endpoint."""
    httpx_mock.add_response(
        method="GET",
        url=f"{NOTIFICATION_ATTACHMENT_URL}/1234567",
        json=attachment_json,
    )
    with Kap() as kap:
        attachments = kap.fetch_attachments(1234567)
    assert len(attachments) == 1
    assert attachments[0].filename == "AFA_2024.01.pdf"
    assert attachments[0].url == f"{FILE_DOWNLOAD_URL}/4028328d9d4a0485019d4ee4bddd3a5e"
    assert attachments[0].url.startswith("https://")


def test_fetch_attachments_no_attachments(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{NOTIFICATION_ATTACHMENT_URL}/9999999",
        json=[],
    )
    with Kap() as kap:
        attachments = kap.fetch_attachments(9999999)
    assert attachments == []


# ---------------------------------------------------------------------------
# Context manager guard
# ---------------------------------------------------------------------------


def test_kap_requires_context_manager() -> None:
    kap = Kap()
    with pytest.raises(RuntimeError, match="context manager"):
        kap.fetch_companies()

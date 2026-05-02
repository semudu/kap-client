"""Tests for domain model parsing."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from kap_client._endpoints import CompanyRow, DisclosureRow, FundGroup, FundRow
from kap_client._models import Attachment, Company, Disclosure, Fund

# ---------------------------------------------------------------------------
# DisclosureRow → Disclosure
# ---------------------------------------------------------------------------


def test_disclosure_from_row_basic(company_disclosures_json: list) -> None:
    row = DisclosureRow.model_validate(company_disclosures_json[0])
    d = Disclosure.from_row(row)
    assert d.index == 1234567
    assert d.company_name == "TÜRK HAVA YOLLARI A.O."
    assert d.stock_codes == "THYAO"
    assert d.has_attachment is True
    assert d.is_corrective is False
    assert d.url == "https://www.kap.org.tr/tr/Bildirim/1234567"
    # company disclosures have no fund_code
    assert d.fund_code == ""


def test_disclosure_from_row_fund(fund_disclosures_json: list) -> None:
    """Fund disclosures populate fund_code, summary, and company_name from kapTitle."""
    row = DisclosureRow.model_validate(fund_disclosures_json[0])
    d = Disclosure.from_row(row)
    assert d.fund_code == "AFA"
    assert d.company_name == "AK PORTFÖY PARA PİYASASI FONU"
    assert d.summary == "Mart 2024 portföy dağılım raporu."


def test_disclosure_summary_empty_when_absent(fund_disclosures_json: list) -> None:
    row = DisclosureRow.model_validate(fund_disclosures_json[1])
    d = Disclosure.from_row(row)
    assert d.summary == ""


def test_disclosure_publish_datetime_parsed(company_disclosures_json: list) -> None:
    row = DisclosureRow.model_validate(company_disclosures_json[0])
    d = Disclosure.from_row(row)
    assert isinstance(d.publish_datetime, datetime)
    assert d.publish_datetime.year == 2024
    assert d.publish_datetime.month == 3
    assert d.publish_datetime.day == 15


def test_disclosure_from_row_no_attachment() -> None:
    raw = {
        "disclosureIndex": 99,
        "publishDate": "2024-01-01 00:00:00",
        "memberTitle": "ACME A.Ş.",
        "hasAttachment": False,
    }
    row = DisclosureRow.model_validate(raw)
    d = Disclosure.from_row(row)
    assert d.has_attachment is False
    assert d.subject == ""
    assert d.stock_codes == ""


def test_disclosure_coerces_bool_strings() -> None:
    raw = {
        "disclosureIndex": 1,
        "publishDate": "2024-01-01 00:00:00",
        "hasAttachment": "true",
        "isLate": "FALSE",
        "isCorrective": "1",
        "isEnglish": "0",
    }
    row = DisclosureRow.model_validate(raw)
    assert row.hasAttachment is True
    assert row.isLate is False
    assert row.isCorrective is True
    assert row.isEnglish is False


def test_disclosure_is_frozen() -> None:
    raw = {
        "disclosureIndex": 1,
        "publishDate": "2024-01-01 00:00:00",
    }
    d = Disclosure.from_row(DisclosureRow.model_validate(raw))
    with pytest.raises(ValidationError):
        d.index = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CompanyRow → Company
# ---------------------------------------------------------------------------


def test_company_from_row(company_list_json: list) -> None:
    row = CompanyRow.model_validate(company_list_json[0])
    c = Company.from_row(row)
    assert c.oid == "4028e4a252438b3301524396b9510024"
    assert c.name == "TÜRK HAVA YOLLARI A.O."
    assert c.ticker == "THYAO"


def test_company_from_row_no_ticker() -> None:
    raw = {"memberOid": "abc123", "memberTitle": "PORTFÖY A.Ş.", "stockCodes": None}
    row = CompanyRow.model_validate(raw)
    c = Company.from_row(row)
    assert c.ticker == ""


def test_company_is_frozen(company_list_json: list) -> None:
    row = CompanyRow.model_validate(company_list_json[0])
    c = Company.from_row(row)
    with pytest.raises(ValidationError):
        c.name = "Changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FundRow → Fund
# ---------------------------------------------------------------------------


def test_fund_from_row(fund_list_json: list) -> None:
    row = FundRow.model_validate(fund_list_json[0])
    f = Fund.from_row(row, FundGroup.YATIRIM_FONLARI)
    assert f.code == "AFA"
    assert f.oid == "4028e4a240f2ef4c01412adf824d0506"
    assert f.fund_group == FundGroup.YATIRIM_FONLARI
    assert f.is_active is True


def test_fund_from_row_all_groups(fund_list_json: list) -> None:
    for group in FundGroup:
        row = FundRow.model_validate(fund_list_json[0])
        f = Fund.from_row(row, group)
        assert f.fund_group == group


def test_fund_group_new_values() -> None:
    """GSF, PFF, TEYF must be present and have correct codes."""
    assert FundGroup.GIRISIM_SERMAYESI_FONLARI.value == "GSF"
    assert FundGroup.PROJE_FINANSMAN_FONLARI.value == "PFF"
    assert FundGroup.TASFIYE_EDILEN_YATIRIM_FONLARI.value == "TEYF"


def test_fund_is_frozen(fund_list_json: list) -> None:
    row = FundRow.model_validate(fund_list_json[0])
    f = Fund.from_row(row, FundGroup.YATIRIM_FONLARI)
    with pytest.raises(ValidationError):
        f.code = "XXX"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Attachment
# ---------------------------------------------------------------------------


def test_attachment_fields() -> None:
    a = Attachment(filename="report.pdf", url="https://www.kap.org.tr/tr/api/file/download/abc123")
    assert a.filename == "report.pdf"
    assert "file/download" in a.url


def test_attachment_is_frozen() -> None:
    a = Attachment(filename="x.pdf", url="https://example.com/x.pdf")
    with pytest.raises(ValidationError):
        a.filename = "y.pdf"  # type: ignore[misc]

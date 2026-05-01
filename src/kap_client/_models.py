"""Domain models returned by the public ``Kap`` facade.

All models are **frozen** Pydantic models so they can safely be cached,
hashed, and compared by value.  They are intentionally decoupled from the
wire-format DTOs in ``_endpoints.py`` via ``from_row`` class-methods.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ._endpoints import BASE_URL, CompanyRow, DisclosureRow, FundGroup, FundRow

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y",
    "%Y-%m-%d",
)


def _parse_datetime(value: str) -> datetime:
    """Try multiple date-time formats and return the first that succeeds."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime string: {value!r}")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class Company(BaseModel, frozen=True):
    """A KAP member company (listed entity or financial institution).

    Attributes
    ----------
    oid:
        KAP-internal hex OID, required for disclosure queries.
    name:
        Full official name (``memberTitle``).
    ticker:
        Primary stock code(s) as returned by KAP (may be empty string for
        non-listed entities such as portfolio management companies).
    """

    oid: str
    name: str
    ticker: str

    @classmethod
    def from_row(cls, row: CompanyRow) -> Company:
        return cls(
            oid=row.memberOid or "",
            name=row.memberTitle or "",
            ticker=row.stockCodes or "",
        )


class Fund(BaseModel, frozen=True):
    """A KAP-registered investment fund.

    Attributes
    ----------
    oid:
        KAP-internal hex OID, required for fund disclosure queries.
    code:
        Short fund code (e.g. ``"AFA"``).
    title:
        Full fund title.
    fund_type:
        Fund type string as returned by KAP (e.g. ``"Hisse Senedi Fonu"``).
    fund_group:
        :class:`FundGroup` enum value (``BYF``, ``YF``, …).
    is_active:
        ``True`` if the fund is currently active (not liquidated).
    """

    oid: str
    code: str
    title: str
    fund_type: str
    fund_group: FundGroup
    is_active: bool

    @classmethod
    def from_row(cls, row: FundRow, fund_group: FundGroup) -> Fund:
        return cls(
            oid=row.oid or "",
            code=row.fundCode or "",
            title=row.fundTitle or "",
            fund_type=row.fundType or "",
            fund_group=fund_group,
            is_active=row.isActive if row.isActive is not None else True,
        )


class Disclosure(BaseModel, frozen=True):
    """A single KAP public disclosure (bildirim).

    Attributes
    ----------
    index:
        KAP disclosure index (numeric identifier).
    publish_datetime:
        Publication date/time (UTC+3, no timezone info stored).
    company_name:
        Full name of the disclosing entity.
    stock_codes:
        Comma-separated list of associated stock codes (may be empty).
    subject:
        Disclosure subject / category.
    disclosure_type:
        Type code returned by KAP (``"FS"``, ``"DG"``, ``"FR"``, …).
    has_attachment:
        Whether the disclosure has file attachments.
    is_late:
        Whether the disclosure was filed late.
    is_corrective:
        Whether this is a corrective disclosure.
    is_english:
        Whether the disclosure text is in English.
    url:
        Full URL to the disclosure detail page.
    """

    index: int
    publish_datetime: datetime
    company_name: str
    stock_codes: str
    subject: str
    disclosure_type: str
    has_attachment: bool
    is_late: bool
    is_corrective: bool
    is_english: bool
    url: str

    @classmethod
    def from_row(cls, row: DisclosureRow) -> Disclosure:
        raw_date = row.publishDate or ""
        try:
            pub_dt = _parse_datetime(raw_date)
        except ValueError:
            pub_dt = datetime.min

        return cls(
            index=row.disclosureIndex,
            publish_datetime=pub_dt,
            company_name=row.memberTitle or "",
            stock_codes=row.stockCodes or "",
            subject=row.subject or "",
            disclosure_type=row.disclosureType or "",
            has_attachment=row.hasAttachment if row.hasAttachment is not None else False,
            is_late=row.isLate if row.isLate is not None else False,
            is_corrective=row.isCorrective if row.isCorrective is not None else False,
            is_english=row.isEnglish if row.isEnglish is not None else False,
            url=f"{BASE_URL}/tr/Bildirim/{row.disclosureIndex}",
        )


class Attachment(BaseModel, frozen=True):
    """A file attachment belonging to a KAP disclosure.

    Attributes
    ----------
    filename:
        Human-readable file name as shown on the KAP page (may be empty).
    url:
        Full absolute URL to download the attachment.
    """

    filename: str
    url: str

"""High-level KAP API facade.

Usage::

    from kap_client import Kap

    with Kap() as kap:
        disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-12-31")
        funds = kap.fetch_funds("YF")
        attachments = kap.fetch_attachments(disclosures[0].index)
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from ._client import KapHttpClient
from ._endpoints import (
    COMPANY_ITEMS_URL,
    FILE_DOWNLOAD_URL,
    FUND_DISCLOSURE_QUERY_URL,
    FUND_LIST_URL,
    FUND_MEMBERS_URL,
    MEMBER_DISCLOSURE_QUERY_URL,
    NOTIFICATION_ATTACHMENT_URL,
    CompanyRow,
    DisclosureRow,
    FundDisclosureQueryBody,
    FundGroup,
    FundRow,
    MemberDisclosureQueryBody,
)
from ._models import Attachment, Company, Disclosure, Fund
from .exceptions import CompanyNotFoundError

logger = logging.getLogger(__name__)

DateLike = str | date | datetime


def _date_str(d: DateLike) -> str:
    """Normalise any date-like value to ``'YYYY-MM-DD'``."""
    if isinstance(d, str):
        return d
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%d")


class Kap:
    """Facade for the KAP (Kamuyu Aydınlatma Platformu) API.

    Provides friendly methods for fetching disclosures, company and fund lists,
    and disclosure attachments.  All network I/O happens inside the context
    manager block.

    Caches
    ------
    Company list and fund lists are cached per instance to avoid redundant
    network requests.  Pass ``refresh=True`` to any cached method to force
    a fresh fetch.

    Parameters
    ----------
    timeout:
        Per-request timeout in seconds (default: ``30.0``).

    Examples
    --------
    ::

        with Kap() as kap:
            # Fetch all active YF funds
            funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)

            # Fetch THYAO disclosures for 2024
            disclosures = kap.fetch_disclosures(
                "THYAO", start_date="2024-01-01", end_date="2024-12-31"
            )

            # Download attachments from the first disclosure
            attachments = kap.fetch_attachments(disclosures[0].index)
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._http: KapHttpClient | None = None

        # --- instance-level caches ---
        # ticker → Company  (populated by _resolve_companies)
        self._companies_cache: dict[str, Company] = {}
        # oid → Company (same objects, alternate index)
        self._companies_by_oid_cache: dict[str, Company] = {}
        # "{fund_group}-{active|all}" → [Fund]
        self._funds_cache: dict[str, list[Fund]] = {}
        # fund_group → [Company]  (portfolio management companies)
        self._fund_members_cache: dict[str, list[Company]] = {}

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Kap:
        self._http = KapHttpClient(timeout=self._timeout).__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        if self._http is not None:
            self._http.__exit__(*args)
            self._http = None

    # ------------------------------------------------------------------
    # Company / member methods
    # ------------------------------------------------------------------

    def fetch_companies(self, *, refresh: bool = False) -> list[Company]:
        """Return all KAP-registered companies (listed and non-listed).

        Results are cached for the lifetime of the context manager.

        Parameters
        ----------
        refresh:
            Force a fresh network request, bypassing the instance cache.
        """
        if not refresh and self._companies_cache:
            return list(self._companies_cache.values())
        self._load_companies()
        return list(self._companies_cache.values())

    def find_company(self, ticker: str, *, refresh: bool = False) -> Company:
        """Resolve a ticker symbol to a :class:`Company`.

        Parameters
        ----------
        ticker:
            Stock code as listed on BIST (case-insensitive).
        refresh:
            Force a fresh company list fetch.

        Raises
        ------
        CompanyNotFoundError:
            If the ticker cannot be found in the KAP member list.
        """
        ticker_upper = ticker.upper()
        if not refresh and ticker_upper in self._companies_cache:
            return self._companies_cache[ticker_upper]
        self._load_companies()
        if ticker_upper not in self._companies_cache:
            raise CompanyNotFoundError(ticker)
        return self._companies_cache[ticker_upper]

    # ------------------------------------------------------------------
    # Fund methods
    # ------------------------------------------------------------------

    def fetch_funds(
        self,
        fund_group: FundGroup | str,
        *,
        include_liquidated: bool = False,
        refresh: bool = False,
    ) -> list[Fund]:
        """Return all funds for the given *fund_group*.

        Parameters
        ----------
        fund_group:
            :class:`FundGroup` enum or its string value (``"YF"``, ``"EYF"``, …).
        include_liquidated:
            If ``True``, also fetch liquidated funds (status ``T``) in addition
            to active funds (status ``Y``).  The combined list is returned.
        refresh:
            Force a fresh network request.
        """
        http = self._require_http()
        group = FundGroup(fund_group) if isinstance(fund_group, str) else fund_group
        cache_key = f"{group.value}-{'all' if include_liquidated else 'active'}"

        if not refresh and cache_key in self._funds_cache:
            return self._funds_cache[cache_key]

        rows = http.get(f"{FUND_LIST_URL}/{group.value}/Y")
        funds = [Fund.from_row(FundRow.model_validate(r), group) for r in rows]

        if include_liquidated:
            liq_rows = http.get(f"{FUND_LIST_URL}/{group.value}/T")
            funds += [Fund.from_row(FundRow.model_validate(r), group) for r in liq_rows]

        self._funds_cache[cache_key] = funds
        return funds

    def fetch_fund_members(
        self,
        fund_group: FundGroup | str,
        *,
        refresh: bool = False,
    ) -> list[Company]:
        """Return portfolio management companies for the given *fund_group*.

        Parameters
        ----------
        fund_group:
            :class:`FundGroup` enum or its string value.
        refresh:
            Force a fresh network request.
        """
        http = self._require_http()
        group = FundGroup(fund_group) if isinstance(fund_group, str) else fund_group
        cache_key = group.value

        if not refresh and cache_key in self._fund_members_cache:
            return self._fund_members_cache[cache_key]

        rows = http.get(f"{FUND_MEMBERS_URL}/{group.value}")
        members = [Company.from_row(CompanyRow.model_validate(r)) for r in rows]
        self._fund_members_cache[cache_key] = members
        return members

    # ------------------------------------------------------------------
    # Disclosure methods
    # ------------------------------------------------------------------

    def fetch_disclosures(
        self,
        company: str,
        start_date: DateLike,
        end_date: DateLike,
        *,
        subject_oids: list[str] | None = None,
    ) -> list[Disclosure]:
        """Fetch company disclosures for the given date range.

        Parameters
        ----------
        company:
            Ticker symbol (e.g. ``"THYAO"``).  Passed as-is into
            ``mkkMemberOidList`` if it looks like an OID, otherwise the
            company list is fetched to resolve the OID.
        start_date:
            Range start (inclusive).  String ``"YYYY-MM-DD"``, ``date``, or
            ``datetime``.
        end_date:
            Range end (inclusive).
        subject_oids:
            Optional list of KAP subject OID strings to filter by.

        Returns
        -------
        list[Disclosure]:
            Disclosures sorted by publication datetime, newest first.
        """
        http = self._require_http()

        # Resolve ticker → OID if needed
        if self._looks_like_oid(company):
            member_oid = company
        else:
            co = self.find_company(company)
            member_oid = co.oid

        body = MemberDisclosureQueryBody(
            fromDate=_date_str(start_date),
            toDate=_date_str(end_date),
            mkkMemberOidList=[member_oid],
            subjectList=subject_oids or [],
        )
        rows = http.post(MEMBER_DISCLOSURE_QUERY_URL, body)
        disclosures = [Disclosure.from_row(DisclosureRow.model_validate(r)) for r in rows]
        return sorted(disclosures, key=lambda d: d.publish_datetime, reverse=True)

    def fetch_fund_disclosures(
        self,
        start_date: DateLike,
        end_date: DateLike,
        *,
        fund_code: str | None = None,
        fund_group: FundGroup | str | None = None,
        subject_oids: list[str] | None = None,
    ) -> list[Disclosure]:
        """Fetch fund disclosures for the given date range.

        Parameters
        ----------
        start_date:
            Range start (inclusive).  String ``"YYYY-MM-DD"``, ``date``, or
            ``datetime``.
        end_date:
            Range end (inclusive).
        fund_code:
            Optional fund code (e.g. ``"THF"``).  Results are filtered
            client-side since the API does not support fund-code filtering.
        fund_group:
            Optional :class:`FundGroup` enum or string (``"YF"``, ``"EYF"``, …).
            When provided, restricts results to that fund type.
        subject_oids:
            Optional list of KAP subject OID strings to filter by.
        """
        http = self._require_http()
        group = FundGroup(fund_group) if isinstance(fund_group, str) else fund_group

        body = FundDisclosureQueryBody(
            fromDate=_date_str(start_date),
            toDate=_date_str(end_date),
            fundOidList=[],
            fundTypeList=[group.value] if group else [],
            subjectList=subject_oids or [],
        )
        rows = http.post(FUND_DISCLOSURE_QUERY_URL, body)
        disclosures = [Disclosure.from_row(DisclosureRow.model_validate(r)) for r in rows]

        if fund_code:
            code_upper = fund_code.upper()
            disclosures = [d for d in disclosures if d.fund_code.upper() == code_upper]

        return sorted(disclosures, key=lambda d: d.publish_datetime, reverse=True)

    def fetch_attachments(self, disclosure_index: int) -> list[Attachment]:
        """Return all attachments for the given disclosure index.

        Uses the ``/tr/api/notification/attachment-detail/{index}`` JSON endpoint.

        Parameters
        ----------
        disclosure_index:
            The ``index`` field from a :class:`Disclosure` object.
        """
        http = self._require_http()
        url = f"{NOTIFICATION_ATTACHMENT_URL}/{disclosure_index}"
        raw_list = http.get(url)

        attachments: list[Attachment] = []
        for item in raw_list:
            for att in item.get("attachments") or []:
                obj_id = att.get("objId", "")
                file_name = att.get("fileName", "")
                # PDF/file download URL pattern on KAP
                att_url = f"{FILE_DOWNLOAD_URL}/{obj_id}" if obj_id else ""
                attachments.append(Attachment(filename=file_name, url=att_url))
        return attachments

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_http(self) -> KapHttpClient:
        if self._http is None:
            raise RuntimeError("Kap must be used as a context manager: `with Kap() as kap: ...`")
        return self._http

    def _load_companies(self) -> None:
        """Fetch KAP member companies by type and populate caches."""
        http = self._require_http()
        # Fetch all member types that list companies
        member_types = ["HT", "YK", "PYS", "BDK", "DCS", "DDK", "DK", "KVH"]
        self._companies_cache.clear()
        self._companies_by_oid_cache.clear()
        for mtype in member_types:
            try:
                rows = http.get(f"{COMPANY_ITEMS_URL}/{mtype}/A")
            except Exception:
                continue
            for raw in rows:
                row = CompanyRow.model_validate(raw)
                company = Company.from_row(row)
                if company.oid:
                    self._companies_by_oid_cache[company.oid] = company
                if company.ticker:
                    for code in company.ticker.split(","):
                        code = code.strip().upper()
                        if code:
                            self._companies_cache[code] = company

    @staticmethod
    def _looks_like_oid(value: str) -> bool:
        """Return True if *value* looks like a KAP hex OID (32 hex chars)."""
        return len(value) >= 24 and all(c in "0123456789abcdefABCDEF" for c in value)

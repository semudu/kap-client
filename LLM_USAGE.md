# kap-client for LLMs

This document explains how an LLM should use kap-client safely and correctly when generating Python code, assistant responses, or automation scripts.

## 1. What kap-client is

kap-client is a synchronous, type-safe Python client for KAP (Kamuyu Aydınlatma Platformu) — Turkey's Public Disclosure Platform.

Primary use cases:
- Fetch company disclosures (KAP bildirim) by ticker symbol or OID
- Fetch fund disclosures (fon bildirimi) for any fund group
- Browse active or liquidated fund lists for all KAP fund groups (YF, BYF, EYF, OKS, GMF, …)
- Look up portfolio management companies per fund group
- Download attachment file links from a disclosure detail page

## 2. Install and import

Use Python 3.10+.

Install:
- pip install kap-client
- uv pip install kap-client
- poetry add kap-client

Import:
- from kap_client import Kap
- Optional models: Disclosure, Attachment, Company, Fund, FundGroup, FundSubject
- Optional exceptions: KapError, RateLimitError, EmptyResponseError, CompanyNotFoundError

## 3. Core mental model for LLMs

The main entrypoint is Kap used as a context manager.

Pattern:
1. Open client with `with Kap() as kap:`
2. Call one of the methods:
   - kap.fetch_companies(...)          -> list[Company]
   - kap.find_company(ticker)          -> Company
   - kap.fetch_funds(fund_group, ...)  -> list[Fund]
   - kap.fetch_fund_members(...)       -> list[Company]
   - kap.fetch_disclosures(...)        -> list[Disclosure]
   - kap.fetch_fund_disclosures(...)   -> list[Disclosure]
   - kap.fetch_fund_disclosures_by_filter(fund_oid, subject_oid, days=365) -> list[Disclosure]
   - kap.fetch_attachments(index)      -> list[Attachment]
3. All returned objects are frozen Pydantic models

Important:
- API is synchronous (no native async)
- All network I/O must happen inside the context manager
- Company list and fund lists are cached per Kap instance automatically
- Calling methods outside the context manager raises RuntimeError

## 4. Main API contract

Constructor:
- Kap(timeout: float = 30.0)
  - timeout: per-request HTTP timeout in seconds

### Company methods

- kap.fetch_companies(*, refresh: bool = False) -> list[Company]
  - Returns all KAP member companies (listed and non-listed)
  - Results cached for the lifetime of the context manager
  - refresh=True forces a fresh network request

- kap.find_company(ticker: str, *, refresh: bool = False) -> Company
  - Resolves a BIST ticker to a Company object
  - Ticker is case-insensitive ("thyao" == "THYAO")
  - Raises CompanyNotFoundError if ticker is not found

### Fund methods

- kap.fetch_funds(fund_group: FundGroup | str, *, include_liquidated: bool = False, refresh: bool = False) -> list[Fund]
  - fund_group: FundGroup enum or string value ("YF", "BYF", "EYF", …)
  - include_liquidated=True also returns liquidated/tasfiye funds
  - Results cached per (group, include_liquidated) combination

- kap.fetch_fund_members(fund_group: FundGroup | str, *, refresh: bool = False) -> list[Company]
  - Returns portfolio management companies (kurucu/yönetici) for the group

### Disclosure methods

- kap.fetch_disclosures(
    company: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    *,
    subject_oids: list[str] | None = None,
  ) -> list[Disclosure]
  - company: ticker symbol ("THYAO") or raw KAP OID hex string
  - Ticker strings are auto-resolved via fetch_companies; OIDs are used directly
  - Dates: "YYYY-MM-DD" strings, date, or datetime objects
  - subject_oids: optional list of FundSubject OID values to filter results
  - Returns disclosures sorted by publish_datetime, newest first

- kap.fetch_fund_disclosures(
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    *,
    fund_code: str | None = None,
    fund_group: FundGroup | str | None = None,
    subject_oids: list[str] | None = None,
  ) -> list[Disclosure]
  - start_date / end_date: MUST be within the same calendar year (cross-year → HTTP 500)
  - fund_code: short code filter e.g. "THF" (applied client-side)
  - fund_group: optional group filter e.g. FundGroup.YATIRIM_FONLARI
  - subject_oids: optional list of FundSubject OID values
  - Use a year-by-year loop for multi-year searches (see snippet below)

- kap.fetch_fund_disclosures_by_filter(
    fund_oid: str,
    subject_oid: str,
    days: int = 365,
  ) -> list[Disclosure]
  - Preferred alternative to fetch_fund_disclosures when the fund OID is known
  - Uses GET /tr/api/disclosure/filter/FILTERYFBF/{fund_oid}/{subject_oid}/{days}
  - NO same-calendar-year constraint; filtering is server-side
  - fund_oid: 32-character hex string from Fund.oid (obtained via fetch_funds())
  - subject_oid: FundSubject OID value (e.g. FundSubject.PORTFOY_DAGILIM_RAPORU.value)
  - days: look-back window, default 365; no API-enforced upper limit
  - Returns disclosures sorted by publish_datetime, newest first

- kap.fetch_attachments(disclosure_index: int) -> list[Attachment]
  - Fetches attachment metadata from the KAP JSON API
  - disclosure_index: the index field from a Disclosure object
  - Returns Attachment objects with direct download URLs of the form:
    https://www.kap.org.tr/tr/api/file/download/{objId}
  - Returns empty list if the disclosure has no attachments

## 5. Data objects returned

Company:
- oid: str    (KAP hex OID, used as memberOid in queries)
- name: str   (official registered name)
- ticker: str (BIST stock code; empty string for non-listed entities)

Fund:
- oid: str          (KAP hex OID, used in fund disclosure queries)
- code: str         (short fund code, e.g. "AFA")
- title: str        (full fund name)
- fund_type: str    (e.g. "Hisse Senedi Fonu")
- fund_group: FundGroup
- is_active: bool   (False for liquidated funds)

Disclosure:
- index: int                      (unique KAP disclosure number)
- publish_datetime: datetime      (publication time)
- company_name: str
- fund_code: str                  (short fund code e.g. "THF"; empty for company disclosures)
- stock_codes: str                (may be empty for non-listed issuers)
- subject: str                    (disclosure topic)
- summary: str                    (short summary / teaser; may be empty)
- disclosure_type: str
- has_attachment: bool
- is_late: bool
- is_corrective: bool
- is_english: bool
- url: str                        (full URL to the KAP disclosure page)

Attachment:
- filename: str   (original file name)
- url: str        (direct download URL)

## 6. FundGroup enum values

```python
FundGroup.BORSA_YATIRIM_FONLARI          = "BYF"
FundGroup.YATIRIM_FONLARI                = "YF"
FundGroup.EMEKLILIK_YATIRIM_FONLARI      = "EYF"
FundGroup.OKS_EMEKLILIK_YATIRIM_FONLARI  = "OKS"
FundGroup.YABANCI_YATIRIM_FONLARI        = "YYF"
FundGroup.VARLIK_FINANSMAN_FONLARI       = "VFF"
FundGroup.KONUT_FINANSMAN_FONLARI        = "KFF"
FundGroup.GAYRIMENKUL_YATIRIM_FONLARI    = "GMF"
FundGroup.GIRISIM_SERMAYESI_FONLARI      = "GSF"
FundGroup.PROJE_FINANSMAN_FONLARI        = "PFF"
FundGroup.TASFIYE_EDILEN_YATIRIM_FONLARI = "TEYF"
```

String values (e.g. "YF") are accepted everywhere FundGroup is accepted.

## 7. Canonical code snippets LLM should generate

Fetch company disclosures by ticker:

```python
from kap_client import Kap

with Kap() as kap:
    disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-12-31")
    for d in disclosures:
        print(d.publish_datetime, d.subject, d.url)
```

Fetch disclosures and download attachments:

```python
from kap_client import Kap

with Kap() as kap:
    disclosures = kap.fetch_disclosures("EREGL", "2024-01-01", "2024-12-31")
    for d in disclosures:
        if d.has_attachment:
            attachments = kap.fetch_attachments(d.index)
            for a in attachments:
                print(a.filename, a.url)
```

Browse active Yatırım Fonu (YF) funds:

```python
from kap_client import Kap, FundGroup

with Kap() as kap:
    funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)
    print(f"{len(funds)} active YF funds")
```

Fetch fund disclosures (new signature — no Fund object required):

```python
from kap_client import Kap, FundGroup

with Kap() as kap:
    disclosures = kap.fetch_fund_disclosures(
        "2024-01-01", "2024-12-31",
        fund_group=FundGroup.YATIRIM_FONLARI,
        fund_code="AFA",
    )
    for d in disclosures:
        print(d.publish_datetime, d.subject, d.summary)
```

Fetch fund disclosures across multiple years (year-loop — required by KAP API):

```python
from datetime import date
from kap_client import Kap, FundGroup
from kap_client._endpoints import FundSubject

with Kap() as kap:
    for year in range(date.today().year, 2019, -1):
        disclosures = kap.fetch_fund_disclosures(
            f"{year}-01-01", f"{year}-12-31",
            fund_group=FundGroup.YATIRIM_FONLARI,
            fund_code="THF",
            subject_oids=[FundSubject.PORTFOY_DAGILIM_RAPORU.value],
        )
        if disclosures:
            latest = disclosures[0]
            attachments = kap.fetch_attachments(latest.index)
            for a in attachments:
                print(f"{a.filename}  →  {a.url}")
            break
```

Fetch fund disclosures via per-fund filter endpoint (preferred — no year constraint, server-side filter):

```python
from kap_client import Kap, FundGroup, FundSubject

with Kap() as kap:
    # Get fund OID once from the fund list
    funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)
    fund = next(f for f in funds if f.code == "THF")

    disclosures = kap.fetch_fund_disclosures_by_filter(
        fund_oid=fund.oid,
        subject_oid=FundSubject.PORTFOY_DAGILIM_RAPORU.value,
        days=365,
    )
    if disclosures:
        latest = disclosures[0]  # sorted newest first
        attachments = kap.fetch_attachments(latest.index)
        for a in attachments:
            print(f"{a.filename}  →  {a.url}")
```

Fetch latest izahname (prospectus) for a fund:

```python
from datetime import date
from kap_client import Kap, FundGroup
from kap_client._endpoints import FundSubject

with Kap() as kap:
    for year in range(date.today().year, 2012, -1):
        disclosures = kap.fetch_fund_disclosures(
            f"{year}-01-01", f"{year}-12-31",
            fund_group=FundGroup.YATIRIM_FONLARI,
            fund_code="TLY",
            subject_oids=[FundSubject.IZAHNAME.value],
        )
        if disclosures:
            attachments = kap.fetch_attachments(disclosures[0].index)
            for a in attachments:
                print(f"{a.filename}  →  {a.url}")
            break
```

Filter disclosures by subject (using FundSubject OID):

```python
from kap_client import Kap, FundSubject

with Kap() as kap:
    disclosures = kap.fetch_disclosures(
        "THYAO",
        "2024-01-01",
        "2024-12-31",
        subject_oids=[FundSubject.OZEL_DURUM_ACIKLAMASI.value],
    )
```

Resolve ticker to Company and use OID directly:

```python
from kap_client import Kap

with Kap() as kap:
    co = kap.find_company("TCELL")
    print(co.oid, co.name)
    disclosures = kap.fetch_disclosures(co.oid, "2024-01-01", "2024-03-31")
```

Reuse one context manager for multiple calls:

```python
from kap_client import Kap, FundGroup

with Kap() as kap:
    # Company cache is shared across all calls in the same block
    thyao = kap.find_company("THYAO")
    tcell = kap.find_company("TCELL")   # no extra HTTP request

    thyao_disclosures = kap.fetch_disclosures(thyao.oid, "2024-01-01", "2024-12-31")
    tcell_disclosures = kap.fetch_disclosures(tcell.oid, "2024-01-01", "2024-12-31")
```

## 8. Error handling policy for LLM outputs

Preferred exception order:
1. CompanyNotFoundError for unknown tickers
2. EmptyResponseError for no rows returned
3. RateLimitError for throttling
4. KapError as generic fallback

Example:

```python
from kap_client import Kap, KapError, RateLimitError, EmptyResponseError, CompanyNotFoundError

try:
    with Kap() as kap:
        disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-12-31")
except CompanyNotFoundError as e:
    print(f"Ticker not found: {e.ticker}")
except EmptyResponseError:
    print("No disclosures in selected range")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except KapError as e:
    print(f"KAP error: {e}")
```

## 9. Constraints LLM must respect

Operational constraints from KAP:
- KAP may block datacenter IPs with 403/503 (WAF protection)
- Rate limiting may apply; client retries 3 times with exponential back-off
- **`start_date` and `end_date` in `fetch_fund_disclosures` must be within the same calendar year** — cross-year ranges return HTTP 500. Use a year-by-year loop for multi-year searches.
- `fetch_fund_disclosures_by_filter` does **not** have this constraint; use it when fund OID is available.
- Disclosures are returned by the API filtered by the exact date range given
- OID strings are 32-character hex strings; tickers are short BIST codes

Library behaviour:
- Retries up to 3 times on 429 or transient errors with back-off
- Raises RateLimitError after all retries exhausted on HTTP 429
- Raises EmptyResponseError when the API returns an empty list
- Raises RuntimeError if any method is called outside the context manager

LLM guidance:
- Pass ticker strings for listed companies, OID strings for non-listed entities
- Reuse one context manager for all related calls — cache is shared
- Prefer fetching a wide date range once over multiple narrow requests
- **Always keep `start_date` / `end_date` within the same year for `fetch_fund_disclosures`**; use a year loop for multi-year searches
- For `fetch_fund_disclosures`, pass `fund_code="XXX"` to filter by fund (no Fund object needed)
- String "YF" / "BYF" etc. are equivalent to FundGroup enum values
- `include_liquidated=True` is needed when searching historical data for defunct funds
- `TASFIYE_EDILEN_YATIRIM_FONLARI ("TEYF")` is the dedicated group for liquidated YF funds

## 10. When LLM should propose alternatives

If user needs async:
- State that kap-client is synchronous
- Suggest asyncio.to_thread(...) wrapper

If user gets 403/503 repeatedly:
- Explain likely WAF/IP block
- Suggest residential network or appropriate proxy strategy

If user gets EmptyResponseError:
- Suggest widening the date range
- Check that the ticker/OID is correct and the company was listed at that time

If user gets CompanyNotFoundError:
- Verify the BIST ticker spelling (all-caps, e.g. "THYAO" not "Thyao")
- Non-listed entities (portfolio management cos) do not have tickers; use fetch_companies() and filter by name

If user needs attachment files:
- Always check disclosure.has_attachment before calling fetch_attachments
- fetch_attachments returns direct download URLs; downloading is up to the caller

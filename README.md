# kap-client

[![PyPI - Version](https://img.shields.io/pypi/v/kap-client.svg)](https://pypi.org/project/kap-client/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/kap-client.svg)](https://pypi.org/project/kap-client/)
[![PyPI - License](https://img.shields.io/pypi/l/kap-client.svg)](LICENSE)
[![CI](https://github.com/semudu/kap-client/actions/workflows/ci.yml/badge.svg)](https://github.com/semudu/kap-client/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://github.com/semudu/kap-client#readme)

**kap-client** is a type-safe Python client for [KAP (Kamuyu Aydınlatma Platformu)](https://www.kap.org.tr) — Turkey's Public Disclosure Platform.

Fetch company and fund disclosures, browse investment fund lists, and download disclosure attachments — all through a clean, synchronous, Pythonic API. Perfect for building financial dashboards, compliance tools, and investment research apps.

> **v0.1** — Production-ready, fully tested, zero breaking changes.

## ✨ Features

- **📢 Company disclosures** — search by BIST ticker or KAP OID, with optional subject filtering
- **📋 Fund disclosures** — search across all KAP fund groups (YF, BYF, EYF, OKS, GMF, …)
- **� Per-fund filter endpoint** — `fetch_fund_disclosures_by_filter` queries a single fund by KAP OID, no calendar-year limit, server-side filtering
- **�🏢 Company & fund lists** — fully enumerated and cached per session
- **📎 Attachment parsing** — automatically extracts file links from disclosure HTML pages
- **🔎 Subject filtering** — narrow results using `FundSubject` OID constants
- **⏱️ Retry & back-off** — 3 attempts with exponential back-off; `RateLimitError` on 429
- **🛡️ Type-safe** — full Pydantic v2 validation, frozen domain models, mypy compatible
- **⚡ Minimal dependencies** — only `httpx` and `pydantic`
- **🐍 Modern Python** — 3.10+ with context manager support

## 📦 Installation

```bash
pip install kap-client
```

### Other package managers

```bash
# uv
uv pip install kap-client

# Poetry
poetry add kap-client
```

## 🚀 Quick start

```python
from kap_client import Kap, FundGroup

with Kap() as kap:
    # Fetch THYAO disclosures for Q1 2024
    disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-03-31")
    for d in disclosures:
        print(d.publish_datetime, d.subject, d.url)

    # Download attachments from the first disclosure
    if disclosures and disclosures[0].has_attachment:
        attachments = kap.fetch_attachments(disclosures[0].index)
        for a in attachments:
            print(a.filename, a.url)

    # Browse active Yatırım Fonları
    funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)
    print(f"{len(funds)} active YF funds found")
```

## 📖 Usage Examples

### Basic: Fetch company disclosures by ticker

```python
from kap_client import Kap

with Kap() as kap:
    disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-12-31")
    for d in disclosures:
        print(f"[{d.publish_datetime:%Y-%m-%d %H:%M}] {d.subject}")
        print(f"  → {d.url}")
```

### Disclosures with attachment download

```python
from kap_client import Kap

with Kap() as kap:
    disclosures = kap.fetch_disclosures("EREGL", "2024-01-01", "2024-12-31")
    for d in disclosures:
        if d.has_attachment:
            attachments = kap.fetch_attachments(d.index)
            for a in attachments:
                print(f"  {a.filename}  →  {a.url}")
```

### Resolve ticker to Company object

```python
from kap_client import Kap

with Kap() as kap:
    co = kap.find_company("TCELL")
    print(f"{co.name} (OID: {co.oid})")

    # Use OID directly for subsequent queries — no extra HTTP request
    disclosures = kap.fetch_disclosures(co.oid, "2024-01-01", "2024-03-31")
    print(f"{len(disclosures)} disclosures found")
```

### Batch: Reuse one context manager for multiple companies

```python
from kap_client import Kap

tickers = ["THYAO", "EREGL", "TCELL", "AKBNK"]

with Kap() as kap:
    # Company list is fetched once and cached for all find_company() calls
    for ticker in tickers:
        co = kap.find_company(ticker)
        disclosures = kap.fetch_disclosures(co.oid, "2024-01-01", "2024-12-31")
        print(f"{ticker}: {len(disclosures)} disclosures")
```

### Browse and filter investment funds

```python
from kap_client import Kap, FundGroup

with Kap() as kap:
    # List active Yatırım Fonları (YF)
    funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)
    print(f"{len(funds)} active YF funds")

    # Include liquidated funds too
    all_funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI, include_liquidated=True)
    inactive = [f for f in all_funds if not f.is_active]
    print(f"{len(inactive)} liquidated funds")

    # List portfolio management companies for BYF group
    members = kap.fetch_fund_members(FundGroup.BORSA_YATIRIM_FONLARI)
    for m in members:
        print(m.name)
```

### Fund disclosures

> **Note:** The KAP API requires `start_date` and `end_date` to fall within the **same calendar year**. Use a year-by-year loop for multi-year searches.

```python
from kap_client import Kap, FundGroup

with Kap() as kap:
    disclosures = kap.fetch_fund_disclosures(
        "2024-01-01", "2024-12-31",
        fund_group=FundGroup.YATIRIM_FONLARI,
        fund_code="AFA",
    )
    for d in disclosures:
        print(f"[{d.publish_datetime:%Y-%m-%d}] {d.subject}")
```

### Latest portfolio report via per-fund filter endpoint (no date-range limit)

Use `fetch_fund_disclosures_by_filter` when you know the fund's KAP OID. This endpoint has **no same-year constraint** and filters server-side — much faster for large date ranges.

```python
from kap_client import Kap, FundSubject

# Fund OID is the `oid` field from a Fund object returned by fetch_funds()
THF_OID = "4028328c950ba8c70195140f682921da"

with Kap() as kap:
    disclosures = kap.fetch_fund_disclosures_by_filter(
        fund_oid=THF_OID,
        subject_oid=FundSubject.PORTFOY_DAGILIM_RAPORU.value,
        days=365,
    )
    if disclosures:
        latest = disclosures[0]  # sorted newest first
        attachments = kap.fetch_attachments(latest.index)
        for a in attachments:
            print(f"{a.filename}  →  {a.url}")
```

To look up a fund's OID dynamically:

```python
from kap_client import Kap, FundGroup, FundSubject

with Kap() as kap:
    funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)
    fund = next(f for f in funds if f.code == "THF")

    disclosures = kap.fetch_fund_disclosures_by_filter(
        fund_oid=fund.oid,
        subject_oid=FundSubject.PORTFOY_DAGILIM_RAPORU.value,
        days=365,
    )
    for d in disclosures:
        print(f"[{d.publish_datetime:%Y-%m-%d}] {d.subject}")
```

### Latest portfolio report (portföy dağılım raporu) via byCriteria endpoint

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

### Latest izahname (prospectus) for a fund

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

### Filter by subject using FundSubject

```python
from kap_client import Kap, FundSubject

with Kap() as kap:
    disclosures = kap.fetch_disclosures(
        "THYAO",
        "2024-01-01",
        "2024-12-31",
        subject_oids=[FundSubject.OZEL_DURUM_ACIKLAMASI.value],
    )
    print(f"{len(disclosures)} özel durum açıklaması")
```

### Integration: Export to Pandas

```python
import pandas as pd
from kap_client import Kap

with Kap() as kap:
    disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-12-31")

df = pd.DataFrame([
    {
        "date": d.publish_datetime.date(),
        "subject": d.subject,
        "type": d.disclosure_type,
        "has_attachment": d.has_attachment,
        "is_corrective": d.is_corrective,
        "url": d.url,
    }
    for d in disclosures
])

print(df.head())
print(f"\nTotal disclosures: {len(df)}")
print(f"With attachments: {df['has_attachment'].sum()}")
```

### Error handling

```python
from kap_client import Kap, KapError, RateLimitError, EmptyResponseError, CompanyNotFoundError

try:
    with Kap() as kap:
        co = kap.find_company("XXXXXX")
        disclosures = kap.fetch_disclosures(co.oid, "2024-01-01", "2024-12-31")
except CompanyNotFoundError as e:
    print(f"Ticker not found: {e.ticker}")
except EmptyResponseError:
    print("No disclosures in selected date range")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except KapError as e:
    print(f"KAP error: {e}")
```

## 📚 API Reference

### `Kap(timeout: float = 30.0)`

Context manager for managing HTTP connections and caches.

```python
with Kap(timeout=15.0) as kap:
    disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-12-31")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `float` | `30.0` | Per-request HTTP timeout in seconds |

---

### `Kap.fetch_companies(*, refresh=False) -> list[Company]`

Returns all KAP-registered companies. Results are **cached per instance** — the second call returns the cached list without a network request. Pass `refresh=True` to force a fresh fetch.

```python
with Kap() as kap:
    companies = kap.fetch_companies()
    print(f"{len(companies)} companies")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `refresh` | `bool` | `False` | Bypass cache and fetch fresh data |

---

### `Kap.find_company(ticker, *, refresh=False) -> Company`

Resolve a BIST ticker to a `Company` object. Ticker matching is case-insensitive.

```python
with Kap() as kap:
    co = kap.find_company("thyao")   # same as "THYAO"
    print(co.oid, co.name)
```

Raises `CompanyNotFoundError` if the ticker is not in the KAP member list.

---

### `Kap.fetch_funds(fund_group, *, include_liquidated=False, refresh=False) -> list[Fund]`

Returns the fund list for a given group. Results are **cached per (group, include_liquidated) combination**.

```python
with Kap() as kap:
    funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)
    funds = kap.fetch_funds("YF")                           # string value accepted
    all_funds = kap.fetch_funds("EYF", include_liquidated=True)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `fund_group` | `FundGroup \| str` | — | Fund group enum or string value (`"YF"`, `"BYF"`, …) |
| `include_liquidated` | `bool` | `False` | Also return liquidated / tasfiye funds |
| `refresh` | `bool` | `False` | Bypass cache and fetch fresh data |

---

### `Kap.fetch_fund_members(fund_group, *, refresh=False) -> list[Company]`

Returns portfolio management companies (kurucu/yönetici) for the given fund group.

---

### `Kap.fetch_disclosures(company, start_date, end_date, *, subject_oids=None) -> list[Disclosure]`

Fetch company disclosures for a date range. Returns results sorted newest first.

```python
with Kap() as kap:
    # By ticker
    disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-12-31")

    # By OID (no extra company lookup)
    disclosures = kap.fetch_disclosures(co.oid, "2024-01-01", "2024-12-31")

    # With subject filter
    disclosures = kap.fetch_disclosures(
        "THYAO", "2024-01-01", "2024-12-31",
        subject_oids=[FundSubject.OZEL_DURUM_ACIKLAMASI.value],
    )
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `company` | `str` | — | BIST ticker (`"THYAO"`) or raw KAP OID hex string |
| `start_date` | `str \| date \| datetime` | — | Range start, inclusive (`"YYYY-MM-DD"` or date/datetime) |
| `end_date` | `str \| date \| datetime` | — | Range end, inclusive |
| `subject_oids` | `list[str] \| None` | `None` | Optional `FundSubject` OID values to filter results |

---

### `Kap.fetch_fund_disclosures(start_date, end_date, *, fund_code=None, fund_group=None, subject_oids=None) -> list[Disclosure]`

Fetch fund disclosures for a date range. Returns results sorted newest first.

> **Constraint:** `start_date` and `end_date` must fall within the **same calendar year**. Cross-year ranges return HTTP 500. Use a year loop for multi-year searches.

```python
with Kap() as kap:
    disclosures = kap.fetch_fund_disclosures(
        "2024-01-01", "2024-12-31",
        fund_group=FundGroup.YATIRIM_FONLARI,
        fund_code="THF",
    )
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_date` | `str \| date \| datetime` | — | Range start, inclusive (`"YYYY-MM-DD"`) |
| `end_date` | `str \| date \| datetime` | — | Range end, inclusive (must be same year as start) |
| `fund_code` | `str \| None` | `None` | Short fund code filter, e.g. `"THF"` (client-side) |
| `fund_group` | `FundGroup \| str \| None` | `None` | Fund group filter, e.g. `FundGroup.YATIRIM_FONLARI` |
| `subject_oids` | `list[str] \| None` | `None` | Optional `FundSubject` OID values |

---

### `Kap.fetch_fund_disclosures_by_filter(fund_oid, subject_oid, days=365) -> list[Disclosure]`

Fetch disclosures for a **single fund** using the KAP per-fund filter endpoint (`GET /tr/api/disclosure/filter/FILTERYFBF/{fund_oid}/{subject_oid}/{days}`). Results are sorted newest first.

**Key advantage:** unlike `fetch_fund_disclosures`, this endpoint has **no calendar-year constraint** and filtering is done server-side, making it faster and more reliable for large date ranges.

```python
with Kap() as kap:
    funds = kap.fetch_funds(FundGroup.YATIRIM_FONLARI)
    fund = next(f for f in funds if f.code == "TLY")

    disclosures = kap.fetch_fund_disclosures_by_filter(
        fund_oid=fund.oid,
        subject_oid=FundSubject.IZAHNAME.value,
        days=730,
    )
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `fund_oid` | `str` | — | KAP fund OID (32-char hex, from `Fund.oid`) |
| `subject_oid` | `str` | — | `FundSubject` OID value (use `FundSubject.XXX.value`) |
| `days` | `int` | `365` | Look-back window in days; no upper limit enforced by the API |

---

### `Kap.fetch_attachments(disclosure_index: int) -> list[Attachment]`

Fetches attachment metadata for a disclosure via the KAP JSON API and returns direct download URLs. Returns an empty list if the disclosure has no attachments.

Download URLs have the form `https://www.kap.org.tr/tr/api/file/download/{objId}`.

```python
with Kap() as kap:
    disclosures = kap.fetch_disclosures("THYAO", "2024-01-01", "2024-12-31")
    for d in disclosures:
        if d.has_attachment:
            for a in kap.fetch_attachments(d.index):
                print(a.filename, a.url)
```

---

## 🗂️ Domain Models

### `Disclosure`

| Field | Type | Description |
|-------|------|-------------|
| `index` | `int` | Unique KAP disclosure number |
| `publish_datetime` | `datetime` | Publication timestamp |
| `company_name` | `str` | Issuer name |
| `fund_code` | `str` | Short fund code (e.g. `"THF"`); empty for company disclosures |
| `stock_codes` | `str` | BIST ticker(s); empty for non-listed issuers |
| `subject` | `str` | Disclosure topic |
| `summary` | `str` | Short summary / teaser text; may be empty |
| `disclosure_type` | `str` | Type classification |
| `has_attachment` | `bool` | Whether file attachments are available |
| `is_late` | `bool` | Filed after deadline |
| `is_corrective` | `bool` | Correction of a prior disclosure |
| `is_english` | `bool` | English-language disclosure |
| `url` | `str` | Full URL to the KAP disclosure page |

### `Attachment`

| Field | Type | Description |
|-------|------|-------------|
| `filename` | `str` | Original file name |
| `url` | `str` | Direct download URL |

### `Company`

| Field | Type | Description |
|-------|------|-------------|
| `oid` | `str` | KAP hex OID (32 chars) |
| `name` | `str` | Official registered name |
| `ticker` | `str` | BIST stock code; empty for non-listed entities |

### `Fund`

| Field | Type | Description |
|-------|------|-------------|
| `oid` | `str` | KAP hex OID (32 chars) |
| `code` | `str` | Short fund code (e.g. `"AFA"`) |
| `title` | `str` | Full fund name |
| `fund_type` | `str` | e.g. `"Hisse Senedi Fonu"` |
| `fund_group` | `FundGroup` | Enum value |
| `is_active` | `bool` | `False` for liquidated funds |

---

## 🏷️ `FundGroup` Enum

| Value | Label |
|-------|-------|
| `FundGroup.BORSA_YATIRIM_FONLARI` | `"BYF"` — Borsa Yatırım Fonları |
| `FundGroup.YATIRIM_FONLARI` | `"YF"` — Yatırım Fonları |
| `FundGroup.EMEKLILIK_YATIRIM_FONLARI` | `"EYF"` — Emeklilik Yatırım Fonları |
| `FundGroup.OKS_EMEKLILIK_YATIRIM_FONLARI` | `"OKS"` — OKS Emeklilik Yatırım Fonları |
| `FundGroup.YABANCI_YATIRIM_FONLARI` | `"YYF"` — Yabancı Yatırım Fonları |
| `FundGroup.VARLIK_FINANSMAN_FONLARI` | `"VFF"` — Varlık Finansman Fonları |
| `FundGroup.KONUT_FINANSMAN_FONLARI` | `"KFF"` — Konut Finansman Fonları |
| `FundGroup.GAYRIMENKUL_YATIRIM_FONLARI` | `"GMF"` — Gayrimenkul Yatırım Fonları |
| `FundGroup.GIRISIM_SERMAYESI_FONLARI` | `"GSF"` — Girişim Sermayesi Fonları |
| `FundGroup.PROJE_FINANSMAN_FONLARI` | `"PFF"` — Proje Finansman Fonları |
| `FundGroup.TASFIYE_EDILEN_YATIRIM_FONLARI` | `"TEYF"` — Tasfiye Edilen Yatırım Fonları |

String values (e.g. `"YF"`) are accepted everywhere a `FundGroup` is expected.

---

## ⚠️ Exceptions

| Exception | When raised |
|-----------|-------------|
| `KapError` | Base exception for all kap-client errors |
| `RateLimitError` | HTTP 429 after all retries exhausted; has `.retry_after: float \| None` |
| `EmptyResponseError` | Successful response but empty data list |
| `CompanyNotFoundError` | Ticker not found in KAP member list; has `.ticker: str` |

## 🛠️ Development

```bash
git clone https://github.com/semudu/kap-client
cd kap-client
pip install -e ".[dev]"
make test        # run tests
make lint        # ruff lint + format check
make typecheck   # mypy strict
```

## License

MIT

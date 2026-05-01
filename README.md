# kap-client

A Python client for [KAP (Kamuyu Aydınlatma Platformu)](https://www.kap.org.tr) —
Turkey's Public Disclosure Platform.

Fetch company and fund disclosures, browse investment fund lists, and download
disclosure attachments — all through a clean, typed, Pythonic API.

## Features

- **Company disclosures** — search by ticker or KAP OID, with optional subject filtering
- **Fund disclosures** — search across all KAP fund groups (YF, BYF, EYF, OKS, GMF, …)
- **Fund & member lists** — fully enumerated, cached per session
- **Attachment parsing** — automatically extracts file links from disclosure HTML pages
- **Retry & back-off** — 3 attempts with exponential back-off; `RateLimitError` on 429
- **Pydantic v2 models** — all return types are frozen, typed domain objects
- **Zero heavy dependencies** — only `httpx` and `pydantic`

## Installation

```bash
pip install kap-client
```

## Quick start

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

    # Fetch fund disclosures
    if funds:
        fd = kap.fetch_fund_disclosures(
            fund=funds[0],
            fund_group=FundGroup.YATIRIM_FONLARI,
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        print(f"{len(fd)} disclosures for {funds[0].code}")
```

## API reference

### `Kap` class

All methods require the context manager (`with Kap() as kap:`).

| Method | Description |
|---|---|
| `fetch_companies(*, refresh=False)` | All KAP-registered companies |
| `find_company(ticker, *, refresh=False)` | Resolve ticker → `Company` |
| `fetch_funds(fund_group, *, include_liquidated=False, refresh=False)` | Fund list |
| `fetch_fund_members(fund_group, *, refresh=False)` | Portfolio mgmt companies |
| `fetch_disclosures(company, start_date, end_date, *, subject_oids=None)` | Company disclosures |
| `fetch_fund_disclosures(fund, fund_group, start_date, end_date, *, subject_oids=None)` | Fund disclosures |
| `fetch_attachments(disclosure_index)` | Attachment list from HTML detail page |

### Domain models

| Model | Key fields |
|---|---|
| `Disclosure` | `index`, `publish_datetime`, `company_name`, `stock_codes`, `subject`, `has_attachment`, `url` |
| `Attachment` | `filename`, `url` |
| `Company` | `oid`, `name`, `ticker` |
| `Fund` | `oid`, `code`, `title`, `fund_type`, `fund_group`, `is_active` |

### `FundGroup` enum

```
BYF  — Borsa Yatırım Fonları
YF   — Yatırım Fonları
EYF  — Emeklilik Yatırım Fonları
OKS  — OKS Emeklilik Yatırım Fonları
YYF  — Yabancı Yatırım Fonları
VFF  — Varlık Finansman Fonları
KFF  — Konut Finansman Fonları
GMF  — Gayrimenkul Yatırım Fonları
```

### Exceptions

| Exception | When raised |
|---|---|
| `KapError` | Base exception for all kap_client errors |
| `RateLimitError` | HTTP 429 after all retries exhausted |
| `EmptyResponseError` | Successful response but empty data list |
| `CompanyNotFoundError` | Ticker not found in KAP member list |

## Development

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

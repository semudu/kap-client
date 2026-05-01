"""Custom exceptions for kap_client."""

from __future__ import annotations


class KapError(Exception):
    """Base exception for all kap_client errors."""


class RateLimitError(KapError):
    """Raised when the KAP API returns HTTP 429 or signals rate limiting."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "KAP rate limit exceeded"
        if retry_after is not None:
            msg += f"; retry after {retry_after:.0f}s"
        super().__init__(msg)


class EmptyResponseError(KapError):
    """Raised when the API returns a success status but no data rows."""


class CompanyNotFoundError(KapError):
    """Raised when a ticker symbol cannot be resolved to a KAP member OID."""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(f"Company not found in KAP member list: {ticker!r}")

"""Low-level HTTP client for the KAP JSON API.

Wraps ``httpx.Client`` with:
- Browser-like headers required by the KAP WAF
- Automatic retry with exponential back-off
- ``RateLimitError`` on HTTP 429
- ``EmptyResponseError`` when the response list is null or empty (optional guard)
"""

from __future__ import annotations

import logging
import time
from html.parser import HTMLParser
from typing import Any, cast

import httpx

from ._endpoints import BASE_URL, REFERER_URL
from .exceptions import EmptyResponseError, KapError, RateLimitError

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds; delay = base ** attempt

_DEFAULT_HEADERS: dict[str, str] = {
    "Origin": BASE_URL,
    "Referer": REFERER_URL,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------------------
# HTML attachment parser
# ---------------------------------------------------------------------------


class _AttachmentLinkParser(HTMLParser):
    """Extract attachment href values from a KAP disclosure detail page.

    KAP renders attachment links as ``<a href="/tr/api/...">`` elements
    inside the disclosure content div.  We collect every href that points
    to the KAP attachment API (``/tr/api/`` prefix) and is not a fragment.
    """

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []  # [(text, href), ...]
        self._current_text: str = ""
        self._capture: bool = False
        self._current_href: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_dict = dict(attrs)
        href = attr_dict.get("href") or ""
        if href and href != "#" and not href.startswith("http"):
            # relative path — attachment candidate
            self._capture = True
            self._current_href = href
            self._current_text = ""

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._current_text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture:
            text = self._current_text.strip()
            if self._current_href:
                self.links.append((text, self._current_href))
            self._capture = False
            self._current_href = ""
            self._current_text = ""


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


class KapHttpClient:
    """Stateful HTTP client for KAP API requests.

    Intended to be used as a context manager::

        with KapHttpClient() as client:
            rows = client.post(MEMBER_DISCLOSURE_QUERY_URL, body)
    """

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout
        self._client: httpx.Client | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> KapHttpClient:
        self._client = httpx.Client(
            headers=_DEFAULT_HEADERS,
            timeout=self._timeout,
            follow_redirects=True,
        )
        return self

    def __exit__(self, *_: object) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post(
        self,
        url: str,
        body: Any,
        *,
        raise_on_empty: bool = False,
    ) -> list[dict[str, Any]]:
        """POST *body* (Pydantic model or dict) to *url* and return the response list.

        KAP POST endpoints return either a bare JSON array or a JSON object
        with a ``data`` / ``list`` key.  This method normalises both shapes
        into a plain ``list[dict]``.

        Parameters
        ----------
        url:
            Full endpoint URL.
        body:
            Pydantic model instance or plain dict.
        raise_on_empty:
            If *True*, raise ``EmptyResponseError`` when the list is empty.
        """
        if self._client is None:
            raise RuntimeError("KapHttpClient must be used as a context manager")

        payload = body.model_dump() if hasattr(body, "model_dump") else body
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                logger.warning("KAP request timed out (attempt %d/%d)", attempt + 1, _MAX_RETRIES)
                last_exc = exc
                self._sleep_backoff(attempt)
                continue
            except httpx.RequestError as exc:
                logger.warning(
                    "KAP network error %s (attempt %d/%d)", exc, attempt + 1, _MAX_RETRIES
                )
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if response.status_code == 429:
                retry_after = self._parse_retry_after(response)
                if attempt < _MAX_RETRIES - 1:
                    logger.warning(
                        "Rate limited by KAP, waiting %.0fs (attempt %d/%d)",
                        retry_after or _BACKOFF_BASE ** (attempt + 1),
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    time.sleep(retry_after or _BACKOFF_BASE ** (attempt + 1))
                    continue
                raise RateLimitError(retry_after)

            if response.status_code != 200:
                raise KapError(
                    f"KAP API returned HTTP {response.status_code}: {response.text[:200]}"
                )

            try:
                data: Any = response.json()
            except Exception as exc:
                raise KapError(f"Invalid JSON from KAP API: {exc}") from exc

            result = self._extract_list(data, url)

            if raise_on_empty and len(result) == 0:
                raise EmptyResponseError(f"KAP returned no data rows for request to {url}")

            return result

        if last_exc is not None:
            raise KapError(f"KAP request failed after {_MAX_RETRIES} attempts") from last_exc
        raise KapError(f"KAP request failed after {_MAX_RETRIES} attempts")

    def get(
        self,
        url: str,
        *,
        raise_on_empty: bool = False,
    ) -> list[dict[str, Any]]:
        """GET *url* and return the response as a list of dicts.

        Used for KAP endpoints that return JSON arrays directly (e.g. fund list,
        fund members list).
        """
        if self._client is None:
            raise RuntimeError("KapHttpClient must be used as a context manager")

        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.get(url)
            except httpx.TimeoutException as exc:
                logger.warning("KAP GET timed out (attempt %d/%d)", attempt + 1, _MAX_RETRIES)
                last_exc = exc
                self._sleep_backoff(attempt)
                continue
            except httpx.RequestError as exc:
                logger.warning(
                    "KAP GET network error %s (attempt %d/%d)", exc, attempt + 1, _MAX_RETRIES
                )
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if response.status_code == 429:
                retry_after = self._parse_retry_after(response)
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(retry_after or _BACKOFF_BASE ** (attempt + 1))
                    continue
                raise RateLimitError(retry_after)

            if response.status_code != 200:
                raise KapError(
                    f"KAP API returned HTTP {response.status_code}: {response.text[:200]}"
                )

            try:
                data: Any = response.json()
            except Exception as exc:
                raise KapError(f"Invalid JSON from KAP API: {exc}") from exc

            result = self._extract_list(data, url)

            if raise_on_empty and len(result) == 0:
                raise EmptyResponseError(f"KAP returned no data rows for GET {url}")

            return result

        if last_exc is not None:
            raise KapError(f"KAP request failed after {_MAX_RETRIES} attempts") from last_exc
        raise KapError(f"KAP request failed after {_MAX_RETRIES} attempts")

    def get_html(self, url: str) -> str:
        """GET *url* and return the raw HTML body as a string.

        Used for disclosure detail pages to parse attachment links.
        """
        if self._client is None:
            raise RuntimeError("KapHttpClient must be used as a context manager")

        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.get(url, headers={"Accept": "text/html"})
            except httpx.TimeoutException as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue
            except httpx.RequestError as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if response.status_code == 429:
                retry_after = self._parse_retry_after(response)
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(retry_after or _BACKOFF_BASE ** (attempt + 1))
                    continue
                raise RateLimitError(retry_after)

            if response.status_code != 200:
                raise KapError(f"KAP returned HTTP {response.status_code} for {url}")

            return response.text

        if last_exc is not None:
            raise KapError(f"KAP request failed after {_MAX_RETRIES} attempts") from last_exc
        raise KapError(f"KAP request failed after {_MAX_RETRIES} attempts")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_list(data: Any, url: str) -> list[dict[str, Any]]:
        """Normalise KAP response shapes into a plain list of dicts."""
        if isinstance(data, list):
            return cast(list[dict[str, Any]], data)
        if isinstance(data, dict):
            # Try common envelope keys
            for key in ("data", "list", "result", "resultList", "items"):
                if key in data and isinstance(data[key], list):
                    return cast(list[dict[str, Any]], data[key])
            # Single-object response — wrap it
            return [cast(dict[str, Any], data)]
        raise KapError(f"Unexpected response shape from {url}: {type(data).__name__}")

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float | None:
        header = response.headers.get("Retry-After")
        if header is None:
            return None
        try:
            return float(header)
        except ValueError:
            return None

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(_BACKOFF_BASE**attempt)

    # ------------------------------------------------------------------
    # HTML utility (stateless, accessible without context manager)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_attachment_links(html: str) -> list[tuple[str, str]]:
        """Parse attachment ``(text, href)`` pairs from a KAP disclosure HTML page."""
        parser = _AttachmentLinkParser()
        parser.feed(html)
        return parser.links

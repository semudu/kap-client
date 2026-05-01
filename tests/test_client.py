"""Tests for KapHttpClient."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from kap_client._client import KapHttpClient
from kap_client._endpoints import FUND_LIST_URL, MEMBER_DISCLOSURE_QUERY_URL
from kap_client.exceptions import KapError, RateLimitError

# ---------------------------------------------------------------------------
# POST tests
# ---------------------------------------------------------------------------


def test_post_returns_list(httpx_mock: HTTPXMock, company_disclosures_json: list) -> None:
    httpx_mock.add_response(
        method="POST",
        url=MEMBER_DISCLOSURE_QUERY_URL,
        json=company_disclosures_json,
    )
    with KapHttpClient() as client:
        result = client.post(MEMBER_DISCLOSURE_QUERY_URL, {})
    assert result == company_disclosures_json


def test_post_unwraps_data_envelope(httpx_mock: HTTPXMock) -> None:
    """If the API wraps its list in a 'data' key, the client unwraps it."""
    payload = [{"disclosureIndex": 1, "publishDate": "2024-01-01 00:00:00"}]
    httpx_mock.add_response(
        method="POST",
        url=MEMBER_DISCLOSURE_QUERY_URL,
        json={"data": payload, "total": 1},
    )
    with KapHttpClient() as client:
        result = client.post(MEMBER_DISCLOSURE_QUERY_URL, {})
    assert result == payload


def test_post_raises_on_http_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=MEMBER_DISCLOSURE_QUERY_URL,
        status_code=503,
        text="Service Unavailable",
    )
    with KapHttpClient() as client, pytest.raises(KapError, match="HTTP 503"):
        client.post(MEMBER_DISCLOSURE_QUERY_URL, {})


def test_post_raises_rate_limit_after_retries(httpx_mock: HTTPXMock) -> None:
    # Add 3 consecutive 429 responses (matches _MAX_RETRIES)
    for _ in range(3):
        httpx_mock.add_response(
            method="POST",
            url=MEMBER_DISCLOSURE_QUERY_URL,
            status_code=429,
            headers={"Retry-After": "5"},
        )
    with KapHttpClient() as client, pytest.raises(RateLimitError) as exc_info:
        client.post(MEMBER_DISCLOSURE_QUERY_URL, {})
    assert exc_info.value.retry_after == 5.0


def test_post_retries_on_429_then_succeeds(
    httpx_mock: HTTPXMock, company_disclosures_json: list
) -> None:
    """Client should retry on 429 and succeed on the next attempt."""
    httpx_mock.add_response(
        method="POST",
        url=MEMBER_DISCLOSURE_QUERY_URL,
        status_code=429,
        headers={"Retry-After": "0"},
    )
    httpx_mock.add_response(
        method="POST",
        url=MEMBER_DISCLOSURE_QUERY_URL,
        json=company_disclosures_json,
    )
    with KapHttpClient(timeout=5.0) as client:
        result = client.post(MEMBER_DISCLOSURE_QUERY_URL, {})
    assert len(result) == len(company_disclosures_json)


def test_post_raises_on_invalid_json(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=MEMBER_DISCLOSURE_QUERY_URL,
        text="not json",
        headers={"Content-Type": "text/html"},
    )
    with KapHttpClient() as client, pytest.raises(KapError, match="Invalid JSON"):
        client.post(MEMBER_DISCLOSURE_QUERY_URL, {})


# ---------------------------------------------------------------------------
# GET tests
# ---------------------------------------------------------------------------


def test_get_returns_list(httpx_mock: HTTPXMock, fund_list_json: list) -> None:
    url = f"{FUND_LIST_URL}/YF/Y"
    httpx_mock.add_response(method="GET", url=url, json=fund_list_json)
    with KapHttpClient() as client:
        result = client.get(url)
    assert result == fund_list_json


def test_get_raises_on_http_error(httpx_mock: HTTPXMock) -> None:
    url = f"{FUND_LIST_URL}/YF/Y"
    httpx_mock.add_response(method="GET", url=url, status_code=404, text="Not Found")
    with KapHttpClient() as client, pytest.raises(KapError, match="HTTP 404"):
        client.get(url)


# ---------------------------------------------------------------------------
# HTML GET tests
# ---------------------------------------------------------------------------


def test_get_html_returns_text(httpx_mock: HTTPXMock, disclosure_detail_html: str) -> None:
    url = "https://www.kap.org.tr/tr/Bildirim/1234567"
    httpx_mock.add_response(method="GET", url=url, text=disclosure_detail_html)
    with KapHttpClient() as client:
        html = client.get_html(url)
    assert "<html" in html


# ---------------------------------------------------------------------------
# HTML parser tests
# ---------------------------------------------------------------------------


def test_attachment_parser_extracts_api_links(disclosure_detail_html: str) -> None:
    links = KapHttpClient.parse_attachment_links(disclosure_detail_html)
    # Should find the /tr/api/ links but not navigation links
    hrefs = [href for _, href in links]
    assert any("/tr/api/" in h for h in hrefs)
    assert not any(h == "#" for h in hrefs)


def test_attachment_parser_no_links() -> None:
    html = "<html><body><p>No attachments here.</p></body></html>"
    links = KapHttpClient.parse_attachment_links(html)
    assert links == []


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_client_requires_context_manager() -> None:
    client = KapHttpClient()
    with pytest.raises(RuntimeError, match="context manager"):
        client.post(MEMBER_DISCLOSURE_QUERY_URL, {})

    with pytest.raises(RuntimeError, match="context manager"):
        client.get(MEMBER_DISCLOSURE_QUERY_URL)

    with pytest.raises(RuntimeError, match="context manager"):
        client.get_html("https://www.kap.org.tr/tr/Bildirim/1")

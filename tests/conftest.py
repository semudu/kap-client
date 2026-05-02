"""Shared pytest fixtures for kap_client tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from operator import methodcaller
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock
from pytest_httpx._options import _HTTPXMockOptions

import kap_client._client as _kap_client_module


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch time.sleep inside _client.py to a no-op so retry back-offs are instant."""
    monkeypatch.setattr(
        _kap_client_module, "time", type("_T", (), {"sleep": staticmethod(lambda s: None)})()
    )


@pytest.fixture
def httpx_mock(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Generator[HTTPXMock, None, None]:
    """Override pytest-httpx fixture with ``assert_all_requests_were_expected=False``.

    ``_load_companies`` issues HTTP requests for 8 member-type URLs; tests only
    mock the ``HT`` endpoint.  The remaining 7 raise ``httpx.ConnectError``
    (silently swallowed inside ``_load_companies``), so we disable the strict
    plan check to avoid spurious teardown errors.
    """
    # Collect per-test marker overrides, but default to non-strict.
    options: dict = {"assert_all_requests_were_expected": False}
    for marker in request.node.iter_markers("httpx_mock"):
        options = marker.kwargs | options

    __tracebackhide__ = methodcaller("errisinstance", TypeError)
    opts = _HTTPXMockOptions(**options)
    mock = HTTPXMock(opts)

    real_handle = httpx.HTTPTransport.handle_request

    def mocked_handle(transport: httpx.HTTPTransport, req: httpx.Request) -> httpx.Response:
        return (
            mock._handle_request(transport, req)
            if opts.should_mock(req)
            else real_handle(transport, req)
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", mocked_handle)

    real_async = httpx.AsyncHTTPTransport.handle_async_request

    async def mocked_async(
        transport: httpx.AsyncHTTPTransport, req: httpx.Request
    ) -> httpx.Response:
        return (
            await mock._handle_async_request(transport, req)
            if opts.should_mock(req)
            else await real_async(transport, req)
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", mocked_async)

    yield mock
    try:
        mock._assert_options()
    finally:
        mock.reset()


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def load_json(name: str) -> list | dict:
    return json.loads(load_fixture(name))


@pytest.fixture()
def company_disclosures_json() -> list:
    return load_json("company_disclosures.json")


@pytest.fixture()
def fund_disclosures_json() -> list:
    return load_json("fund_disclosures.json")


@pytest.fixture()
def fund_list_json() -> list:
    return load_json("fund_list.json")


@pytest.fixture()
def company_list_json() -> list:
    return load_json("company_list.json")


@pytest.fixture()
def disclosure_detail_html() -> str:
    return load_fixture("disclosure_detail.html")


@pytest.fixture()
def attachment_json() -> list:
    return load_json("attachment_detail.json")

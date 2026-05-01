"""Shared pytest fixtures for kap_client tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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

"""Pytest configuration and fixtures for parisbibpy tests."""

import json
from pathlib import Path
from typing import Any

import pytest

from parisbibpy.client import ParisBibClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def use_standard_requests_for_offline_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to standard requests.Session in tests so responses mock adapter intercepts traffic."""
    monkeypatch.setattr(ParisBibClient, "DEFAULT_IMPERSONATE", None)


@pytest.fixture
def account_summary_data() -> dict[str, Any]:
    with open(FIXTURES_DIR / "account_summary.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def list_loans_data() -> dict[str, Any]:
    with open(FIXTURES_DIR / "list_loans.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def user_pairings_data() -> dict[str, Any]:
    with open(FIXTURES_DIR / "user_pairings.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def list_bookings_data() -> dict[str, Any]:
    with open(FIXTURES_DIR / "list_bookings.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def renew_loans_data() -> dict[str, Any]:
    with open(FIXTURES_DIR / "renew_loans.json", encoding="utf-8") as f:
        return json.load(f)

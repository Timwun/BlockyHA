"""Tests for config-flow input normalization."""

from __future__ import annotations

import pytest

from custom_components.blocky.config_flow import (
    normalize_base_url,
    normalize_endpoint_path,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("http://10.0.0.11:4000/", "http://10.0.0.11:4000"),
        ("https://dns.home.lan:8080/blocky/", "https://dns.home.lan:8080/blocky"),
    ),
)
def test_normalize_base_url(value: str, expected: str) -> None:
    """Trailing slashes are removed while proxy prefixes are kept."""
    assert normalize_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    (
        "http://user:pass@blocky.local",
        "blocky.local",
        "http://blocky.local?bad=true",
        "http://blocky.local#bad",
    ),
)
def test_invalid_base_url(value: str) -> None:
    """Credentials and URL components outside the base are rejected."""
    with pytest.raises(ValueError):
        normalize_base_url(value)


def test_normalize_endpoint_path() -> None:
    """Endpoint paths are normalized to a leading slash."""
    assert normalize_endpoint_path("api/stats") == "/api/stats"


@pytest.mark.parametrize("value", ("", "https://other/path", "/api/stats?x=1", "/api/stats#x"))
def test_invalid_endpoint_path(value: str) -> None:
    """Endpoint overrides cannot escape the configured base URL."""
    with pytest.raises(ValueError):
        normalize_endpoint_path(value)

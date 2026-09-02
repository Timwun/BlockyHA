"""Tests for the example native Lovelace dashboard."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_dashboard_is_valid_lovelace_yaml() -> None:
    """The dashboard has a complete view and references the integration entities."""
    dashboard = yaml.safe_load(
        Path(__file__).parents[1].joinpath("blocky-dashboard.yaml").read_text()
    )

    assert dashboard["title"] == "Blocky"
    assert dashboard["views"][0]["path"] == "blocky"
    assert any(
        card.get("entity") == "switch.blocky_blocking"
        for card in dashboard["views"][0]["cards"][1]["cards"]
    )
    assert "YOUR_BLOCKY_CONFIG_ENTRY_ID" in Path(
        __file__
    ).parents[1].joinpath("blocky-dashboard.yaml").read_text()

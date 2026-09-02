"""Tests for the example native Lovelace dashboard."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_dashboard_is_valid_lovelace_yaml() -> None:
    """The dashboard has a complete view and references the integration entities."""
    dashboard_path = Path(__file__).parents[1].joinpath("blocky-dashboard.yaml")
    dashboard_text = dashboard_path.read_text()
    dashboard = yaml.safe_load(dashboard_text)
    cards = dashboard["views"][0]["cards"]
    controls = cards[1]
    summary = cards[3]

    assert dashboard["title"] == "Blocky"
    assert dashboard["views"][0]["path"] == "blocky"
    assert controls["columns"] == 2
    assert controls["cards"][0]["entity"] == "switch.blocky_blocking"
    assert controls["cards"][1]["type"] == "button"
    assert controls["cards"][1]["entity"] == "button.blocky_refresh_lists"
    assert sum(card["name"].startswith("Pause ") for card in controls["cards"]) == 3
    assert summary["columns"] == 2
    assert all(card.get("vertical") is True for card in summary["cards"])
    assert "sensor.blocky_denylist_entries" in dashboard_text
    assert "sensor.blocky_allowlist_entries" in dashboard_text
    assert "sensor.blocky_query_types" in dashboard_text
    assert "YOUR_BLOCKY_CONFIG_ENTRY_ID" in dashboard_text

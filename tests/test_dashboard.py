"""Validate the shipped Lovelace dashboard file."""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

DASHBOARD = Path(__file__).parents[1] / "dashboards" / "chunmi_ihcooker_slim.yaml"


def test_dashboard_is_valid_yaml() -> None:
    data = yaml.safe_load(DASHBOARD.read_text(encoding="utf-8"))
    assert "title" not in data  # dashboard title is set where the YAML file is registered
    views = data["views"]
    assert len(views) >= 1
    assert views[0]["title"] == "烹饪"
    assert views[0]["path"] == "cook"
    cards = views[0]["cards"]
    assert any(card.get("title") == "快捷模式" for card in cards)


def test_dashboard_calls_app_like_services() -> None:
    text = DASHBOARD.read_text(encoding="utf-8")
    assert "chunmi_ihcooker_slim.start_preset" in text
    assert "chunmi_ihcooker_slim.start_simple_recipe" in text
    assert "custom:chunmi-ihcooker-card" in text
    assert "chunmi_ihcooker_slim.search_recipes" in text
    assert "button.press" in text

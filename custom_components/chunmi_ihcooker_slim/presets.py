"""App-like presets for the Chunmi IH Cooker Slim.

The Mi Home app exposes five built-in cooking modes through MIoT action 2/1
(``cook-mode`` 1-5) and richer recipes through action 3/1.  This module maps
those modes to friendly names and generates a compatible single-stage cook
profile for each one, so Home Assistant can offer the same buttons even when
only the recipe action is implemented by a firmware version.
"""

from __future__ import annotations

from dataclasses import dataclass

from .recipe import (
    RECIPE_TYPE_SINGLE_FIRE,
    RECIPE_TYPE_SINGLE_TEMPERATURE,
    build_simple_profile,
)


@dataclass(frozen=True)
class CookPreset:
    """A friendly, app-like cooking preset."""

    key: str
    name: str
    name_en: str
    cook_mode: int
    minutes: int
    fire: int
    temperature: int
    icon: str
    profile_type: int = RECIPE_TYPE_SINGLE_FIRE

    def build_profile(
        self,
        *,
        minutes: int | None = None,
        fire: int | None = None,
        temperature: int | None = None,
        menu_index: int = 9,
    ) -> str:
        """Build the cook_data hex string for this preset."""
        profile_type = self.profile_type
        value = self.fire if profile_type == RECIPE_TYPE_SINGLE_FIRE else self.temperature
        if fire is not None and profile_type == RECIPE_TYPE_SINGLE_FIRE:
            value = fire
        if temperature is not None and profile_type == RECIPE_TYPE_SINGLE_TEMPERATURE:
            value = temperature
        return build_simple_profile(
            minutes=self.minutes if minutes is None else minutes,
            recipe_type=profile_type,
            fire=value if profile_type == RECIPE_TYPE_SINGLE_FIRE else self.fire,
            temperature=value
            if profile_type == RECIPE_TYPE_SINGLE_TEMPERATURE
            else self.temperature,
            menu_index=menu_index,
        )


PRESETS: dict[str, CookPreset] = {
    preset.key: preset
    for preset in (
        CookPreset(
            key="hotpot",
            name="火锅",
            name_en="Hotpot",
            cook_mode=1,
            minutes=30,
            fire=50,
            temperature=100,
            icon="mdi:pot-steam",
        ),
        CookPreset(
            key="steam_boil",
            name="蒸煮",
            name_en="Steam boil",
            cook_mode=2,
            minutes=25,
            fire=45,
            temperature=100,
            icon="mdi:pot",
        ),
        CookPreset(
            key="simmer",
            name="煲汤",
            name_en="Simmer",
            cook_mode=3,
            minutes=90,
            fire=25,
            temperature=95,
            icon="mdi:soup-kitchen",
        ),
        CookPreset(
            key="stir_fry",
            name="煎炒",
            name_en="Stir fry",
            cook_mode=4,
            minutes=15,
            fire=75,
            temperature=180,
            icon="mdi:pan",
            profile_type=RECIPE_TYPE_SINGLE_TEMPERATURE,
        ),
        CookPreset(
            key="deep_fry",
            name="油炸",
            name_en="Deep fry",
            cook_mode=5,
            minutes=12,
            fire=80,
            temperature=190,
            icon="mdi:oil",
            profile_type=RECIPE_TYPE_SINGLE_TEMPERATURE,
        ),
    )
}

PRESET_KEYS = tuple(PRESETS)


def get_preset(key: str) -> CookPreset:
    """Return a preset by key, raising a helpful error for unknown keys."""
    try:
        return PRESETS[key]
    except KeyError as exc:
        raise ValueError(f"Unknown cooking preset: {key}") from exc

"""Named hotel presets for the Hotel board game."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hotel_generator.config import PresetInfo
from hotel_generator.errors import InvalidParamsError


@dataclass
class HotelPreset:
    """Curated hotel complex configuration."""

    name: str
    display_name: str
    description: str
    style_name: str
    num_buildings: int
    building_roles: list[str]
    size_hints: dict[str, dict[str, float]] = field(default_factory=dict)
    bend_angle: float = 0.0  # Degrees to bend the complex around the vertical axis
    layout_override: str | None = None  # Force a specific layout strategy

    def to_preset_info(self) -> PresetInfo:
        return PresetInfo(
            name=self.name,
            display_name=self.display_name,
            description=self.description,
            style_name=self.style_name,
            num_buildings=self.num_buildings,
            building_roles=self.building_roles,
        )


# Preset registry
PRESET_REGISTRY: dict[str, HotelPreset] = {}


def _register(preset: HotelPreset) -> HotelPreset:
    PRESET_REGISTRY[preset.name] = preset
    return preset


_register(HotelPreset(
    name="royal",
    display_name="Royal",
    description="Grand classical hotel with courtyard, wide wings, and clock tower",
    style_name="classical",
    num_buildings=4,
    building_roles=["main", "wing", "wing", "tower"],
    size_hints={
        "main": {"width": 1.1, "depth": 0.8, "floors": 1.0},
        "wing": {"width": 0.8, "depth": 0.55, "floors": 0.85},
        "tower": {"width": 0.3, "depth": 0.3, "floors": 1.5},
    },
))

_register(HotelPreset(
    name="fujiyama",
    display_name="Fujiyama",
    description="Art Deco skyscraper complex with stepped towers",
    style_name="art_deco",
    num_buildings=3,
    building_roles=["main", "annex", "annex"],
    size_hints={
        "main": {"width": 0.9, "depth": 0.75, "floors": 1.25},
        "annex": {"width": 0.5, "depth": 0.4, "floors": 0.85},
    },
))

_register(HotelPreset(
    name="waikiki",
    display_name="Waikiki",
    description="Tropical resort with main lodge and scattered pagoda pavilions",
    style_name="tropical",
    num_buildings=5,
    building_roles=["main", "pavilion", "pavilion", "pavilion", "pavilion"],
    size_hints={
        "main": {"width": 1.1, "depth": 0.8, "floors": 1.0},
        "pavilion": {"width": 0.45, "depth": 0.35, "floors": 0.35},
    },
))

_register(HotelPreset(
    name="president",
    display_name="President",
    description="Imposing modern tower complex with cascading heights",
    style_name="modern",
    num_buildings=4,
    building_roles=["main", "tower", "wing", "annex"],
    size_hints={
        "main": {"width": 1.0, "depth": 0.7, "floors": 3.58},     # 25 floors
        "tower": {"width": 0.75, "depth": 0.55, "floors": 2.86},   # 20 floors
        "wing": {"width": 0.65, "depth": 0.45, "floors": 2.15},    # 15 floors
        "annex": {"width": 0.55, "depth": 0.4, "floors": 1.43},    # 10 floors
    },
))

_register(HotelPreset(
    name="safari",
    display_name="Safari",
    description="Mediterranean lodge with wide, low-slung wings",
    style_name="mediterranean",
    num_buildings=3,
    building_roles=["main", "wing", "wing"],
    size_hints={
        "main": {"width": 1.15, "depth": 0.75, "floors": 0.75},
        "wing": {"width": 0.85, "depth": 0.5, "floors": 0.6},
    },
))

_register(HotelPreset(
    name="taj_mahal",
    display_name="Taj Mahal",
    description="Victorian-Mughal palace with onion-domed turrets and flanking pavilions",
    style_name="victorian",
    num_buildings=3,
    building_roles=["main", "pavilion", "pavilion"],
    size_hints={
        "main": {"width": 1.0, "depth": 0.85, "floors": 1.0},
        "pavilion": {"width": 0.45, "depth": 0.35, "floors": 0.5},
    },
))

_register(HotelPreset(
    name="letoile",
    display_name="L'Etoile",
    description="Curved crescent of elegant narrow townhouses",
    style_name="townhouse",
    num_buildings=4,
    building_roles=["main", "main", "main", "main"],
    size_hints={
        "main": {"width": 0.7, "depth": 1.0, "floors": 1.15},
    },
    bend_angle=60.0,
))

_register(HotelPreset(
    name="vacation",
    display_name="Vacation",
    description="Sweeping curved modern high-rise resort tower",
    style_name="modern",
    num_buildings=1,
    building_roles=["main"],
    size_hints={
        "main": {"width": 3.33, "depth": 0.8, "floors": 2.86},  # ~100x20x100mm
    },
    bend_angle=90.0,
))

_register(HotelPreset(
    name="boomerang",
    display_name="Boomerang",
    description="Curved skyscraper complex swept into a boomerang arc",
    style_name="skyscraper",
    num_buildings=3,
    building_roles=["tower", "wing", "wing"],
    size_hints={
        "tower": {"width": 0.35, "depth": 0.35, "floors": 2.5},
        "wing": {"width": 0.8, "depth": 0.5, "floors": 0.85},
    },
    bend_angle=120.0,
    layout_override="row",
))


def list_presets() -> list[PresetInfo]:
    """List all available presets."""
    return [p.to_preset_info() for p in PRESET_REGISTRY.values()]


def get_preset(name: str) -> HotelPreset:
    """Get a preset by name."""
    if name not in PRESET_REGISTRY:
        available = sorted(PRESET_REGISTRY.keys())
        raise InvalidParamsError(
            f"Unknown preset '{name}'. Available: {', '.join(available)}"
        )
    return PRESET_REGISTRY[name]

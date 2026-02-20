"""Tests for hotel presets."""

import pytest

from hotel_generator.complex.presets import (
    PRESET_REGISTRY,
    list_presets,
    get_preset,
)
from hotel_generator.complex.builder import ComplexBuilder
from hotel_generator.config import ComplexParams
from hotel_generator.errors import InvalidParamsError
from hotel_generator.settings import Settings
from hotel_generator.styles.base import STYLE_REGISTRY


class TestPresetRegistry:
    def test_all_presets_registered(self):
        expected = {"royal", "fujiyama", "waikiki", "president",
                    "safari", "taj_mahal", "letoile", "boomerang", "vacation"}
        assert set(PRESET_REGISTRY.keys()) == expected

    def test_valid_styles(self):
        for name, preset in PRESET_REGISTRY.items():
            assert preset.style_name in STYLE_REGISTRY, (
                f"Preset '{name}' references unknown style '{preset.style_name}'"
            )

    def test_roles_match_count(self):
        for name, preset in PRESET_REGISTRY.items():
            assert len(preset.building_roles) == preset.num_buildings, (
                f"Preset '{name}': {len(preset.building_roles)} roles "
                f"but {preset.num_buildings} buildings"
            )

    def test_list_presets(self):
        presets = list_presets()
        assert len(presets) == 9
        names = [p.name for p in presets]
        assert "royal" in names
        assert "waikiki" in names

    def test_get_preset(self):
        preset = get_preset("royal")
        assert preset.style_name == "classical"
        assert preset.num_buildings == 4

    def test_get_unknown_preset(self):
        with pytest.raises(InvalidParamsError, match="Unknown preset"):
            get_preset("nonexistent")


class TestPresetGeneration:
    @pytest.fixture
    def builder(self):
        return ComplexBuilder(Settings())

    @pytest.mark.parametrize("preset_name", list(PRESET_REGISTRY.keys()))
    def test_preset_generates_valid_complex(self, builder, preset_name):
        params = ComplexParams(
            style_name="modern",  # will be overridden by preset
            preset=preset_name,
            num_buildings=PRESET_REGISTRY[preset_name].num_buildings,
        )
        result = builder.build(params)
        assert len(result.buildings) == PRESET_REGISTRY[preset_name].num_buildings
        for b in result.buildings:
            assert b.is_watertight
        assert not result.combined.is_empty()

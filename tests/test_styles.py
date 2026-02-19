"""Tests for style system and individual styles."""

import pytest

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.errors import InvalidParamsError
from hotel_generator.styles.base import STYLE_REGISTRY, list_styles, assemble_building
from hotel_generator.geometry.primitives import box


class TestStyleRegistry:
    def test_modern_registered(self):
        assert "modern" in STYLE_REGISTRY

    def test_list_styles(self):
        styles = list_styles()
        assert len(styles) >= 1
        names = [s["name"] for s in styles]
        assert "modern" in names

    def test_style_has_required_properties(self):
        style = STYLE_REGISTRY["modern"]
        assert style.name == "modern"
        assert style.display_name
        assert style.description


class TestAssembleBuilding:
    def test_basic_assembly(self):
        shell = box(10, 8, 15)
        result = assemble_building(shell)
        assert not result.is_empty()

    def test_assembly_with_cutouts(self):
        shell = box(10, 8, 15)
        cuts = [box(1, 20, 1)]  # window-like through-cut
        result = assemble_building(shell, cutouts=cuts)
        assert result.volume() < shell.volume()

    def test_assembly_with_additions(self):
        shell = box(10, 8, 15)
        adds = [box(12, 10, 0.5).translate([0, 0, 15])]  # roof
        result = assemble_building(shell, additions=adds)
        assert result.volume() > shell.volume()


class TestModernStyle:
    def test_generates_valid_manifold(self):
        style = STYLE_REGISTRY["modern"]
        params = BuildingParams(
            style_name="modern",
            width=8.0,
            depth=6.0,
            num_floors=4,
            floor_height=0.8,
            printer_type="fdm",
        )
        m = style.generate(params, PrinterProfile.fdm())
        assert not m.is_empty()
        assert m.volume() > 0

    def test_generates_with_resin(self):
        style = STYLE_REGISTRY["modern"]
        params = BuildingParams(
            style_name="modern",
            width=8.0,
            depth=6.0,
            num_floors=4,
            floor_height=0.8,
            printer_type="resin",
        )
        m = style.generate(params, PrinterProfile.resin())
        assert not m.is_empty()

    def test_with_penthouse(self):
        style = STYLE_REGISTRY["modern"]
        params = BuildingParams(
            style_name="modern",
            style_params={"has_penthouse": True},
        )
        m = style.generate(params, PrinterProfile.fdm())
        assert not m.is_empty()

    def test_without_penthouse(self):
        style = STYLE_REGISTRY["modern"]
        params = BuildingParams(
            style_name="modern",
            style_params={"has_penthouse": False},
        )
        m = style.generate(params, PrinterProfile.fdm())
        assert not m.is_empty()

    def test_validate_style_params_bad_window_style(self):
        style = STYLE_REGISTRY["modern"]
        with pytest.raises(InvalidParamsError):
            style.validate_style_params({"window_style": "invalid"})

    def test_deterministic_with_seed(self):
        style = STYLE_REGISTRY["modern"]
        params = BuildingParams(style_name="modern", seed=123)
        profile = PrinterProfile.fdm()
        m1 = style.generate(params, profile)
        m2 = style.generate(params, profile)
        assert abs(m1.volume() - m2.volume()) < 0.01

"""Tests for config models."""

import pytest
from pydantic import ValidationError

from hotel_generator.config import (
    BuildingParams,
    BuildingPlacement,
    ComplexParams,
    PresetInfo,
    PrinterProfile,
    StyleInfo,
    ErrorResponse,
)
from hotel_generator.errors import InvalidParamsError


class TestPrinterProfile:
    def test_fdm_defaults(self):
        p = PrinterProfile.fdm()
        assert p.min_wall_thickness == 0.8
        assert p.use_window_frames is True

    def test_resin_profile(self):
        p = PrinterProfile.resin()
        assert p.min_wall_thickness == 0.5
        assert p.use_window_frames is True
        assert p.use_arched_windows is True

    def test_from_type_fdm(self):
        p = PrinterProfile.from_type("fdm")
        assert p.base_thickness == 2.5

    def test_from_type_resin(self):
        p = PrinterProfile.from_type("resin")
        assert p.base_thickness == 2.0

    def test_from_type_invalid(self):
        with pytest.raises(InvalidParamsError):
            PrinterProfile.from_type("sla")


class TestBuildingParams:
    def test_valid_params(self):
        p = BuildingParams(
            style_name="modern",
            width=30.0,
            depth=25.0,
            num_floors=4,
            floor_height=5.0,
            printer_type="fdm",
        )
        assert p.style_name == "modern"
        assert p.seed == 42

    def test_defaults(self):
        p = BuildingParams(style_name="modern")
        assert p.width == 30.0
        assert p.num_floors == 7
        assert p.printer_type == "fdm"

    def test_aspect_ratio_rejected(self):
        # 20 floors * 5.0 = 100mm height, min base dim = 5mm => ratio 20:1 > 15:1
        with pytest.raises((ValidationError, InvalidParamsError)):
            BuildingParams(
                style_name="modern",
                width=5.0,
                depth=5.0,
                num_floors=20,
                floor_height=5.0,
                printer_type="fdm",
            )

    def test_valid_aspect_ratio(self):
        # 4 floors * 5.0 = 20mm, base = 25mm => ratio 0.8:1
        p = BuildingParams(
            style_name="modern",
            width=30.0,
            depth=25.0,
            num_floors=4,
            floor_height=5.0,
        )
        assert p.num_floors == 4

    def test_invalid_printer_type(self):
        with pytest.raises((ValidationError, InvalidParamsError)):
            BuildingParams(
                style_name="modern",
                printer_type="laser",
            )

    def test_style_params_dict(self):
        p = BuildingParams(
            style_name="modern",
            style_params={"has_penthouse": False},
        )
        assert p.style_params["has_penthouse"] is False


class TestBuildingPlacement:
    def test_defaults(self):
        p = BuildingPlacement()
        assert p.x == 0.0
        assert p.y == 0.0
        assert p.rotation == 0.0
        assert p.role == "main"

    def test_valid_roles(self):
        for role in ("main", "wing", "annex", "tower", "pavilion"):
            p = BuildingPlacement(role=role)
            assert p.role == role

    def test_invalid_role(self):
        with pytest.raises((ValidationError, InvalidParamsError)):
            BuildingPlacement(role="garage")

    def test_roundtrip(self):
        p = BuildingPlacement(
            x=10.0, y=5.0, rotation=90.0,
            width=20.0, depth=15.0, num_floors=3, floor_height=4.0,
            role="wing",
        )
        d = p.model_dump()
        p2 = BuildingPlacement(**d)
        assert p2.x == 10.0
        assert p2.role == "wing"


class TestComplexParams:
    def test_defaults(self):
        p = ComplexParams(style_name="modern")
        assert p.num_buildings == 3
        assert p.building_spacing == 5.0
        assert p.max_triangles == 200_000
        assert p.placements is None
        assert p.preset is None

    def test_valid_range(self):
        for n in range(1, 7):
            p = ComplexParams(style_name="modern", num_buildings=n)
            assert p.num_buildings == n

    def test_too_many_buildings(self):
        with pytest.raises((ValidationError, InvalidParamsError)):
            ComplexParams(style_name="modern", num_buildings=7)

    def test_zero_buildings(self):
        with pytest.raises((ValidationError, InvalidParamsError)):
            ComplexParams(style_name="modern", num_buildings=0)

    def test_spacing_too_small(self):
        with pytest.raises((ValidationError, InvalidParamsError)):
            ComplexParams(style_name="modern", building_spacing=1.0)

    def test_invalid_printer_type(self):
        with pytest.raises((ValidationError, InvalidParamsError)):
            ComplexParams(style_name="modern", printer_type="laser")

    def test_placements_count_mismatch(self):
        with pytest.raises((ValidationError, InvalidParamsError)):
            ComplexParams(
                style_name="modern",
                num_buildings=2,
                placements=[BuildingPlacement()],  # only 1
            )

    def test_placements_count_match(self):
        p = ComplexParams(
            style_name="modern",
            num_buildings=2,
            placements=[BuildingPlacement(), BuildingPlacement(role="wing")],
        )
        assert len(p.placements) == 2

    def test_with_preset(self):
        p = ComplexParams(style_name="modern", preset="royal")
        assert p.preset == "royal"

    def test_with_lot_size(self):
        p = ComplexParams(style_name="modern", lot_width=80.0, lot_depth=60.0)
        assert p.lot_width == 80.0
        assert p.lot_depth == 60.0


class TestPresetInfo:
    def test_basic(self):
        p = PresetInfo(
            name="royal",
            display_name="Royal",
            description="Grand classical hotel",
            style_name="classical",
            num_buildings=4,
            building_roles=["main", "wing", "wing", "tower"],
        )
        assert p.name == "royal"
        assert len(p.building_roles) == 4


class TestResponseModels:
    def test_style_info(self):
        s = StyleInfo(
            name="modern",
            display_name="Modern",
            description="Clean lines",
        )
        assert s.name == "modern"

    def test_error_response(self):
        e = ErrorResponse(
            error_type="InvalidParamsError",
            message="Bad input",
        )
        assert e.error_type == "InvalidParamsError"

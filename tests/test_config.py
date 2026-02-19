"""Tests for config models."""

import pytest
from pydantic import ValidationError

from hotel_generator.config import (
    BuildingParams,
    PrinterProfile,
    StyleInfo,
    ErrorResponse,
)
from hotel_generator.errors import InvalidParamsError


class TestPrinterProfile:
    def test_fdm_defaults(self):
        p = PrinterProfile.fdm()
        assert p.min_wall_thickness == 0.8
        assert p.use_window_frames is False

    def test_resin_profile(self):
        p = PrinterProfile.resin()
        assert p.min_wall_thickness == 0.5
        assert p.use_window_frames is True
        assert p.use_arched_windows is True

    def test_from_type_fdm(self):
        p = PrinterProfile.from_type("fdm")
        assert p.base_thickness == 1.2

    def test_from_type_resin(self):
        p = PrinterProfile.from_type("resin")
        assert p.base_thickness == 1.0

    def test_from_type_invalid(self):
        with pytest.raises(InvalidParamsError):
            PrinterProfile.from_type("sla")


class TestBuildingParams:
    def test_valid_params(self):
        p = BuildingParams(
            style_name="modern",
            width=8.0,
            depth=6.0,
            num_floors=4,
            floor_height=0.8,
            printer_type="fdm",
        )
        assert p.style_name == "modern"
        assert p.seed == 42

    def test_defaults(self):
        p = BuildingParams(style_name="modern")
        assert p.width == 8.0
        assert p.num_floors == 4
        assert p.printer_type == "fdm"

    def test_aspect_ratio_rejected(self):
        # 20 floors * 0.8 = 16mm height, min base dim = 1.5mm => ratio ~10.7:1
        with pytest.raises((ValidationError, InvalidParamsError)):
            BuildingParams(
                style_name="modern",
                width=1.5,
                depth=1.5,
                num_floors=20,
                floor_height=0.8,
                printer_type="fdm",
            )

    def test_valid_aspect_ratio(self):
        # 4 floors * 0.8 = 3.2mm, base = 6mm => ratio 0.53:1
        p = BuildingParams(
            style_name="modern",
            width=8.0,
            depth=6.0,
            num_floors=4,
            floor_height=0.8,
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

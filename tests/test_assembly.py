"""Tests for the assembly engine."""

import pytest

from hotel_generator.assembly.building import HotelBuilder, BuildResult
from hotel_generator.config import BuildingParams
from hotel_generator.errors import InvalidParamsError
from hotel_generator.settings import Settings


@pytest.fixture
def builder():
    return HotelBuilder(Settings())


class TestHotelBuilder:
    def test_build_returns_build_result(self, builder):
        params = BuildingParams(
            style_name="modern",
            width=30.0,
            depth=25.0,
            num_floors=4,
            floor_height=5.0,
            printer_type="fdm",
        )
        result = builder.build(params)
        assert isinstance(result, BuildResult)

    def test_build_result_fields(self, builder):
        params = BuildingParams(style_name="modern")
        result = builder.build(params)
        assert result.is_watertight
        assert result.triangle_count > 0
        assert not result.manifold.is_empty()
        assert result.bounding_box is not None
        assert "style" in result.metadata
        assert result.metadata["style"] == "modern"

    def test_build_with_base(self, builder):
        params = BuildingParams(style_name="modern")
        result = builder.build(params)
        # Base extends below z=0
        min_x, min_y, min_z, max_x, max_y, max_z = result.bounding_box
        assert min_z < 0  # base slab is below building

    def test_invalid_style_raises(self, builder):
        params = BuildingParams(style_name="nonexistent")
        with pytest.raises(InvalidParamsError, match="Unknown style"):
            builder.build(params)

    def test_metadata_includes_timing(self, builder):
        params = BuildingParams(style_name="modern")
        result = builder.build(params)
        assert "generation_time_ms" in result.metadata
        assert result.metadata["generation_time_ms"] >= 0

    def test_fdm_and_resin_both_work(self, builder):
        for pt in ["fdm", "resin"]:
            params = BuildingParams(style_name="modern", printer_type=pt)
            result = builder.build(params)
            assert result.is_watertight

    def test_different_seeds_same_structure(self, builder):
        p1 = BuildingParams(style_name="modern", seed=1)
        p2 = BuildingParams(style_name="modern", seed=2)
        r1 = builder.build(p1)
        r2 = builder.build(p2)
        # Both should be valid
        assert r1.is_watertight
        assert r2.is_watertight

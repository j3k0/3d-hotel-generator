"""Tests for the hotel complex builder."""

import pytest

from hotel_generator.complex.builder import ComplexBuilder, ComplexResult
from hotel_generator.complex.base_plate import complex_base_plate
from hotel_generator.config import BuildingParams, BuildingPlacement, ComplexParams
from hotel_generator.errors import InvalidParamsError
from hotel_generator.settings import Settings


@pytest.fixture
def builder():
    return ComplexBuilder(Settings())


class TestBasePlate:
    def test_basic_plate(self):
        plate = complex_base_plate(80, 60, 2.5, 0.5)
        assert not plate.is_empty()
        assert plate.volume() > 0

    def test_plate_with_recesses(self):
        placements = [
            BuildingPlacement(x=-15, y=0, width=20, depth=15),
            BuildingPlacement(x=15, y=0, width=20, depth=15),
        ]
        plate = complex_base_plate(80, 60, 2.5, 0.5, placements)
        assert not plate.is_empty()
        plate_no_recess = complex_base_plate(80, 60, 2.5, 0.5)
        assert plate.volume() < plate_no_recess.volume()

    def test_plate_below_z0(self):
        plate = complex_base_plate(80, 60, 2.5, 0.5)
        min_x, min_y, min_z, max_x, max_y, max_z = plate.bounding_box()
        assert min_z < 0


class TestComplexBuilder:
    def test_build_returns_complex_result(self, builder):
        params = ComplexParams(style_name="modern", num_buildings=2)
        result = builder.build(params)
        assert isinstance(result, ComplexResult)

    def test_correct_building_count(self, builder):
        for n in [1, 2, 3]:
            params = ComplexParams(style_name="modern", num_buildings=n)
            result = builder.build(params)
            assert len(result.buildings) == n

    def test_each_building_watertight(self, builder):
        params = ComplexParams(style_name="modern", num_buildings=3)
        result = builder.build(params)
        for b in result.buildings:
            assert b.is_watertight

    def test_base_plate_not_empty(self, builder):
        params = ComplexParams(style_name="modern", num_buildings=2)
        result = builder.build(params)
        assert not result.base_plate.is_empty()

    def test_combined_not_empty(self, builder):
        params = ComplexParams(style_name="modern", num_buildings=2)
        result = builder.build(params)
        assert not result.combined.is_empty()
        assert result.combined.volume() > 0

    def test_single_building(self, builder):
        params = ComplexParams(style_name="modern", num_buildings=1)
        result = builder.build(params)
        assert len(result.buildings) == 1
        assert result.buildings[0].is_watertight

    def test_seed_variation(self, builder):
        r1 = builder.build(ComplexParams(style_name="modern", num_buildings=2, seed=1))
        r2 = builder.build(ComplexParams(style_name="modern", num_buildings=2, seed=2))
        # Both valid
        assert len(r1.buildings) == 2
        assert len(r2.buildings) == 2

    def test_invalid_style_raises(self, builder):
        params = ComplexParams(style_name="nonexistent", num_buildings=2)
        with pytest.raises(InvalidParamsError, match="Unknown style"):
            builder.build(params)

    def test_metadata(self, builder):
        params = ComplexParams(style_name="modern", num_buildings=3)
        result = builder.build(params)
        assert result.metadata["style"] == "modern"
        assert result.metadata["num_buildings"] == 3
        assert "generation_time_ms" in result.metadata

    def test_lot_dimensions(self, builder):
        params = ComplexParams(style_name="modern", num_buildings=2)
        result = builder.build(params)
        assert result.lot_width > 0
        assert result.lot_depth > 0

    def test_placements_returned(self, builder):
        params = ComplexParams(style_name="modern", num_buildings=3)
        result = builder.build(params)
        assert len(result.placements) == 3


class TestSkipBase:
    def test_skip_base_no_base_slab(self):
        from hotel_generator.assembly.building import HotelBuilder
        builder = HotelBuilder(Settings())
        params = BuildingParams(style_name="modern")
        result = builder.build(params, skip_base=True)
        # Without base, min_z should be >= 0 (no negative z)
        min_x, min_y, min_z, max_x, max_y, max_z = result.bounding_box
        assert min_z >= -0.2  # small tolerance for boolean embeds

    def test_with_base_has_negative_z(self):
        from hotel_generator.assembly.building import HotelBuilder
        builder = HotelBuilder(Settings())
        params = BuildingParams(style_name="modern")
        result = builder.build(params, skip_base=False)
        min_x, min_y, min_z, max_x, max_y, max_z = result.bounding_box
        assert min_z < 0

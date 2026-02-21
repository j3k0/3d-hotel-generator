"""Tests for the board system: config, road layout, garden layout, property builder."""

import random

import pytest

from hotel_generator.board.config import (
    BoardParams,
    GardenFeaturePlacement,
    PropertyParams,
    PropertySlot,
)
from hotel_generator.board.garden_layout import GardenLayoutEngine, Rect
from hotel_generator.board.road import generate_road_layout
from hotel_generator.config import BuildingPlacement
from hotel_generator.styles.base import GardenTheme


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

class TestPropertyParams:
    def test_defaults(self):
        p = PropertyParams()
        assert p.lot_width == 100.0
        assert p.lot_depth == 80.0
        assert p.road_edge == "south"

    def test_invalid_road_edge(self):
        with pytest.raises(Exception):
            PropertyParams(road_edge="northwest")

    def test_invalid_printer(self):
        with pytest.raises(Exception):
            PropertyParams(printer_type="sla")

    def test_lot_too_small(self):
        with pytest.raises(Exception):
            PropertyParams(lot_width=20.0, lot_depth=10.0)


class TestBoardParams:
    def test_defaults(self):
        p = BoardParams()
        assert p.road_shape == "loop"
        assert p.num_properties == 8

    def test_invalid_road_shape(self):
        with pytest.raises(Exception):
            BoardParams(road_shape="zigzag")

    def test_too_many_properties(self):
        with pytest.raises(Exception):
            BoardParams(num_properties=20)


# ---------------------------------------------------------------------------
# Road layout
# ---------------------------------------------------------------------------

class TestRoadLayout:
    def test_loop_8_properties(self):
        rng = random.Random(42)
        slots = generate_road_layout("loop", 8, 100.0, 80.0, 8.0, rng)
        assert len(slots) == 8
        # Each slot should have a valid road edge
        for s in slots:
            assert s.road_edge in ("north", "south", "east", "west")
            assert s.assigned_preset != ""

    def test_serpentine_8(self):
        rng = random.Random(42)
        slots = generate_road_layout("serpentine", 8, 100.0, 80.0, 8.0, rng)
        assert len(slots) == 8

    def test_linear_8(self):
        rng = random.Random(42)
        slots = generate_road_layout("linear", 8, 100.0, 80.0, 8.0, rng)
        assert len(slots) == 8

    def test_custom_assignments(self):
        rng = random.Random(42)
        assignments = {0: "waikiki", 1: "royal"}
        slots = generate_road_layout("linear", 4, 100.0, 80.0, 8.0, rng, assignments)
        assert slots[0].assigned_preset == "waikiki"
        assert slots[1].assigned_preset == "royal"

    def test_loop_2_properties(self):
        rng = random.Random(42)
        slots = generate_road_layout("loop", 2, 100.0, 80.0, 8.0, rng)
        assert len(slots) == 2

    def test_invalid_shape(self):
        rng = random.Random(42)
        with pytest.raises(Exception):
            generate_road_layout("circular", 4, 100.0, 80.0, 8.0, rng)


# ---------------------------------------------------------------------------
# Garden layout
# ---------------------------------------------------------------------------

class TestGardenLayout:
    def test_basic_layout(self):
        engine = GardenLayoutEngine()
        theme = GardenTheme(
            tree_type="deciduous",
            tree_density=0.5,
            pool_shape="rectangular",
            pool_size="medium",
            has_hedges=True,
            hedge_style="border",
            has_terrace=True,
            path_style="straight",
        )
        placements = [
            BuildingPlacement(x=0, y=40.0, width=30.0, depth=25.0, role="main"),
        ]
        rng = random.Random(42)
        features = engine.compute_layout(
            lot_width=100.0,
            lot_depth=80.0,
            road_edge="south",
            road_width=8.0,
            building_placements=placements,
            garden_theme=theme,
            rng=rng,
        )
        assert len(features) > 0
        types = {f.feature_type for f in features}
        # Should have at least some of the expected feature types
        assert len(types) >= 2  # at least trees + something else

    def test_no_pool_theme(self):
        engine = GardenLayoutEngine()
        theme = GardenTheme(pool_shape=None, has_hedges=False, has_terrace=False)
        placements = [
            BuildingPlacement(x=0, y=40.0, width=30.0, depth=25.0, role="main"),
        ]
        rng = random.Random(42)
        features = engine.compute_layout(
            lot_width=100.0, lot_depth=80.0,
            road_edge="south", road_width=8.0,
            building_placements=placements,
            garden_theme=theme, rng=rng,
        )
        pool_features = [f for f in features if f.feature_type == "pool"]
        assert len(pool_features) == 0

    def test_tropical_dense_trees(self):
        engine = GardenLayoutEngine()
        theme = GardenTheme(
            tree_type="palm", tree_density=0.8,
            pool_shape="kidney", pool_size="large",
            has_hedges=False, has_terrace=True, path_style="curved",
        )
        placements = [
            BuildingPlacement(x=0, y=40.0, width=20.0, depth=15.0, role="main"),
        ]
        rng = random.Random(42)
        features = engine.compute_layout(
            lot_width=100.0, lot_depth=80.0,
            road_edge="south", road_width=8.0,
            building_placements=placements,
            garden_theme=theme, rng=rng,
        )
        tree_features = [f for f in features if "tree" in f.feature_type]
        assert len(tree_features) >= 3  # dense = more trees

    def test_reproducible(self):
        engine = GardenLayoutEngine()
        theme = GardenTheme()
        placements = [BuildingPlacement(x=0, y=40.0, width=30.0, depth=25.0)]
        f1 = engine.compute_layout(100.0, 80.0, "south", 8.0, placements, theme, random.Random(42))
        f2 = engine.compute_layout(100.0, 80.0, "south", 8.0, placements, theme, random.Random(42))
        assert len(f1) == len(f2)
        for a, b in zip(f1, f2):
            assert a.feature_type == b.feature_type
            assert abs(a.x - b.x) < 0.001
            assert abs(a.y - b.y) < 0.001


class TestRect:
    def test_contains(self):
        r = Rect(0, 0, 10, 10)
        assert r.contains(5, 5)
        assert not r.contains(15, 5)
        assert r.contains(11, 5, margin=2.0)  # with margin


# ---------------------------------------------------------------------------
# Property builder (integration test)
# ---------------------------------------------------------------------------

class TestPropertyBuilder:
    """Integration tests — these generate actual geometry."""

    def test_build_modern_property(self):
        from hotel_generator.board.property_builder import PropertyBuilder
        from hotel_generator.settings import Settings

        settings = Settings()
        builder = PropertyBuilder(settings)
        params = PropertyParams(
            style_name="modern",
            num_buildings=2,
            lot_width=100.0,
            lot_depth=80.0,
            seed=42,
        )
        result = builder.build(params)
        assert not result.plate.is_empty()
        assert result.plate.volume() > 0
        assert len(result.buildings) == 2
        assert result.lot_width == 100.0
        assert result.lot_depth == 80.0

    def test_build_tropical_with_garden(self):
        from hotel_generator.board.property_builder import PropertyBuilder
        from hotel_generator.settings import Settings

        settings = Settings()
        builder = PropertyBuilder(settings)
        params = PropertyParams(
            style_name="tropical",
            num_buildings=3,
            lot_width=100.0,
            lot_depth=80.0,
            garden_enabled=True,
            seed=99,
        )
        result = builder.build(params)
        assert not result.plate.is_empty()
        assert len(result.garden_placements) > 0

    def test_build_without_garden(self):
        from hotel_generator.board.property_builder import PropertyBuilder
        from hotel_generator.settings import Settings

        settings = Settings()
        builder = PropertyBuilder(settings)
        params = PropertyParams(
            style_name="modern",
            num_buildings=2,
            garden_enabled=False,
            seed=42,
        )
        result = builder.build(params)
        assert not result.plate.is_empty()
        assert len(result.garden_placements) == 0

    def test_build_with_preset(self):
        from hotel_generator.board.property_builder import PropertyBuilder
        from hotel_generator.settings import Settings

        settings = Settings()
        builder = PropertyBuilder(settings)
        params = PropertyParams(
            preset="royal",
            lot_width=100.0,
            lot_depth=80.0,
            seed=42,
        )
        result = builder.build(params)
        assert not result.plate.is_empty()
        assert result.metadata["preset"] == "royal"

"""Tests for the layout engine and strategies."""

import random

import pytest

from hotel_generator.config import BuildingPlacement, ComplexParams
from hotel_generator.errors import InvalidParamsError
from hotel_generator.layout.placement import (
    BuildingFootprint,
    placement_footprint,
    footprints_overlap,
    any_overlaps,
    compute_lot_bounds,
    footprints_fit_lot,
)
from hotel_generator.layout.strategies import (
    STRATEGIES,
    row_layout,
    courtyard_layout,
    hierarchical_layout,
    cluster_layout,
    campus_layout,
    l_layout,
)
from hotel_generator.layout.engine import LayoutEngine


class TestBuildingFootprint:
    def test_footprint_basic(self):
        p = BuildingPlacement(x=0, y=0, width=10, depth=8)
        f = placement_footprint(p)
        assert f.min_x == -5
        assert f.max_x == 5
        assert f.min_y == -4
        assert f.max_y == 4

    def test_footprint_offset(self):
        p = BuildingPlacement(x=10, y=5, width=6, depth=4)
        f = placement_footprint(p)
        assert f.min_x == 7
        assert f.max_x == 13
        assert f.center_x == 10

    def test_footprint_rotated_90(self):
        p = BuildingPlacement(x=0, y=0, width=10, depth=6, rotation=90)
        f = placement_footprint(p)
        # After 90 rotation, width/depth swap in AABB
        assert f.width == pytest.approx(6)
        assert f.depth == pytest.approx(10)

    def test_footprint_rotated_270(self):
        p = BuildingPlacement(x=0, y=0, width=10, depth=6, rotation=270)
        f = placement_footprint(p)
        assert f.width == pytest.approx(6)
        assert f.depth == pytest.approx(10)


class TestOverlapDetection:
    def test_no_overlap(self):
        a = BuildingFootprint(-5, -4, 5, 4)
        b = BuildingFootprint(10, -4, 20, 4)
        assert not footprints_overlap(a, b)

    def test_overlap(self):
        a = BuildingFootprint(-5, -4, 5, 4)
        b = BuildingFootprint(3, -2, 13, 6)
        assert footprints_overlap(a, b)

    def test_margin_causes_overlap(self):
        a = BuildingFootprint(-5, -4, 5, 4)
        b = BuildingFootprint(6, -4, 16, 4)
        assert not footprints_overlap(a, b, margin=0)
        assert footprints_overlap(a, b, margin=2)

    def test_any_overlaps_none(self):
        ps = [
            BuildingPlacement(x=-20, y=0, width=10, depth=8),
            BuildingPlacement(x=0, y=0, width=10, depth=8),
            BuildingPlacement(x=20, y=0, width=10, depth=8),
        ]
        assert not any_overlaps(ps)

    def test_any_overlaps_detected(self):
        ps = [
            BuildingPlacement(x=0, y=0, width=10, depth=8),
            BuildingPlacement(x=3, y=0, width=10, depth=8),
        ]
        assert any_overlaps(ps)


class TestLotBounds:
    def test_compute_bounds(self):
        ps = [
            BuildingPlacement(x=-10, y=0, width=10, depth=8),
            BuildingPlacement(x=10, y=0, width=10, depth=8),
        ]
        w, d = compute_lot_bounds(ps, margin=2)
        assert w > 0
        assert d > 0

    def test_fits_lot(self):
        ps = [BuildingPlacement(x=0, y=0, width=10, depth=8)]
        assert footprints_fit_lot(ps, 100, 100)
        assert not footprints_fit_lot(ps, 5, 5)


class TestStrategies:
    """Test each strategy produces valid layouts for 1-6 buildings."""

    @pytest.fixture(params=list(STRATEGIES.keys()))
    def strategy_name(self, request):
        return request.param

    def test_correct_count(self, strategy_name):
        fn = STRATEGIES[strategy_name]
        rng = random.Random(42)
        for n in range(1, 7):
            result = fn(n, rng, 30.0, 25.0, 4, 5.0, 5.0)
            assert len(result) == n, f"{strategy_name} with {n} buildings returned {len(result)}"

    def test_no_overlaps(self, strategy_name):
        fn = STRATEGIES[strategy_name]
        rng = random.Random(42)
        for n in range(1, 7):
            result = fn(n, rng, 30.0, 25.0, 4, 5.0, 5.0)
            assert not any_overlaps(result), f"{strategy_name} with {n} has overlaps"

    def test_seed_variation(self, strategy_name):
        fn = STRATEGIES[strategy_name]
        r1 = fn(3, random.Random(1), 30.0, 25.0, 4, 5.0, 5.0)
        r2 = fn(3, random.Random(2), 30.0, 25.0, 4, 5.0, 5.0)
        # At least some strategies should produce different layouts with different seeds
        # (deterministic ones may be the same, so we just check they're valid)
        assert len(r1) == 3
        assert len(r2) == 3


class TestLayoutEngine:
    def test_basic_layout(self):
        engine = LayoutEngine()
        params = ComplexParams(style_name="modern", num_buildings=3)
        placements = engine.compute_layout(params, strategy="row")
        assert len(placements) == 3
        assert not any_overlaps(placements)

    def test_explicit_placements(self):
        engine = LayoutEngine()
        explicit = [
            BuildingPlacement(x=-20, y=0, width=10, depth=8),
            BuildingPlacement(x=20, y=0, width=10, depth=8),
        ]
        params = ComplexParams(
            style_name="modern", num_buildings=2, placements=explicit,
        )
        result = engine.compute_layout(params)
        assert len(result) == 2
        assert result[0].x == -20.0
        assert result[1].x == 20.0

    def test_invalid_strategy(self):
        engine = LayoutEngine()
        params = ComplexParams(style_name="modern", num_buildings=2)
        with pytest.raises(InvalidParamsError, match="Unknown layout"):
            engine.compute_layout(params, strategy="nonexistent")

    def test_all_strategies(self):
        engine = LayoutEngine()
        for strategy_name in STRATEGIES:
            params = ComplexParams(style_name="modern", num_buildings=3)
            placements = engine.compute_layout(params, strategy=strategy_name)
            assert len(placements) == 3


class TestPreferredStrategy:
    def test_all_styles_have_strategy(self):
        from hotel_generator.styles.base import STYLE_REGISTRY
        for name, style in STYLE_REGISTRY.items():
            strategy = style.preferred_layout_strategy()
            assert strategy in STRATEGIES, f"{name} has invalid strategy '{strategy}'"

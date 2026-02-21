"""Tests for landscape components (trees, hedges, pools, paths, terraces)."""

import random

import pytest

from hotel_generator.components.landscape import (
    conifer_tree,
    deciduous_tree,
    garden_path,
    hedge_row,
    palm_tree,
    swimming_pool,
    terrace,
)
from hotel_generator.errors import GeometryError


# ---------------------------------------------------------------------------
# Trees
# ---------------------------------------------------------------------------

class TestDeciduousTree:
    def test_basic(self):
        tree = deciduous_tree()
        assert not tree.is_empty()
        assert tree.volume() > 0

    def test_with_rng_reproducible(self):
        t1 = deciduous_tree(rng=random.Random(42))
        t2 = deciduous_tree(rng=random.Random(42))
        assert abs(t1.volume() - t2.volume()) < 0.001

    def test_custom_size(self):
        small = deciduous_tree(height=2.0, canopy_radius=0.8, trunk_radius=0.3)
        big = deciduous_tree(height=8.0, canopy_radius=3.0, trunk_radius=0.6)
        assert not small.is_empty()
        assert not big.is_empty()
        assert big.volume() > small.volume()

    def test_bounding_box_reasonable(self):
        tree = deciduous_tree(height=4.0, canopy_radius=1.5)
        mn_x, mn_y, mn_z, mx_x, mx_y, mx_z = tree.bounding_box()
        assert mx_z > 2.0  # Should be at least a few mm tall
        assert mx_z < 10.0  # Shouldn't be unreasonably tall


class TestConiferTree:
    def test_basic(self):
        tree = conifer_tree()
        assert not tree.is_empty()
        assert tree.volume() > 0

    def test_with_rng(self):
        tree = conifer_tree(rng=random.Random(99))
        assert not tree.is_empty()

    def test_cone_shape_taller_than_wide(self):
        tree = conifer_tree(height=5.0, canopy_radius=1.2)
        mn_x, mn_y, mn_z, mx_x, mx_y, mx_z = tree.bounding_box()
        total_height = mx_z - mn_z
        total_width = mx_x - mn_x
        assert total_height > total_width


class TestPalmTree:
    def test_basic(self):
        tree = palm_tree()
        assert not tree.is_empty()
        assert tree.volume() > 0

    def test_tall_and_thin(self):
        tree = palm_tree(height=6.0, trunk_radius=0.4)
        mn_x, mn_y, mn_z, mx_x, mx_y, mx_z = tree.bounding_box()
        total_height = mx_z - mn_z
        assert total_height > 4.0  # Palm should be tall


# ---------------------------------------------------------------------------
# Hedges
# ---------------------------------------------------------------------------

class TestHedgeRow:
    def test_basic(self):
        h = hedge_row(length=10.0)
        assert not h.is_empty()
        assert h.volume() > 0

    def test_dimensions(self):
        h = hedge_row(length=20.0, height=1.5, width=1.0)
        mn_x, mn_y, mn_z, mx_x, mx_y, mx_z = h.bounding_box()
        assert abs((mx_x - mn_x) - 20.0) < 0.01
        assert abs((mx_y - mn_y) - 1.0) < 0.01
        assert abs((mx_z - mn_z) - 1.5) < 0.01


# ---------------------------------------------------------------------------
# Swimming pools
# ---------------------------------------------------------------------------

class TestSwimmingPool:
    def test_rectangular(self):
        rim, recess = swimming_pool(shape="rectangular")
        assert not rim.is_empty()
        assert not recess.is_empty()
        assert rim.volume() > 0
        assert recess.volume() > 0

    def test_kidney(self):
        rim, recess = swimming_pool(shape="kidney")
        assert not rim.is_empty()
        assert not recess.is_empty()

    def test_l_shaped(self):
        rim, recess = swimming_pool(shape="l_shaped")
        assert not rim.is_empty()
        assert not recess.is_empty()

    def test_unknown_shape_raises(self):
        with pytest.raises(GeometryError, match="Unknown pool shape"):
            swimming_pool(shape="hexagonal")

    def test_recess_extends_below_z0(self):
        _, recess = swimming_pool(pool_depth=0.5)
        mn_x, mn_y, mn_z, mx_x, mx_y, mx_z = recess.bounding_box()
        assert mn_z < 0  # Recess goes below Z=0


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

class TestGardenPath:
    def test_straight_path(self):
        p = garden_path([(0, 0), (10, 0)])
        assert not p.is_empty()
        assert p.volume() > 0

    def test_multi_segment(self):
        p = garden_path([(0, 0), (5, 0), (5, 5), (10, 5)])
        assert not p.is_empty()

    def test_single_point_raises(self):
        with pytest.raises(GeometryError, match="at least 2 points"):
            garden_path([(0, 0)])

    def test_diagonal_path(self):
        p = garden_path([(0, 0), (10, 10)])
        assert not p.is_empty()


# ---------------------------------------------------------------------------
# Terraces
# ---------------------------------------------------------------------------

class TestTerrace:
    def test_basic(self):
        t = terrace(width=10.0, depth=8.0)
        assert not t.is_empty()
        assert t.volume() > 0

    def test_dimensions(self):
        t = terrace(width=15.0, depth=10.0, height=0.5)
        mn_x, mn_y, mn_z, mx_x, mx_y, mx_z = t.bounding_box()
        assert abs((mx_x - mn_x) - 15.0) < 0.01
        assert abs((mx_y - mn_y) - 10.0) < 0.01
        assert abs((mx_z - mn_z) - 0.5) < 0.01

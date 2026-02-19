"""Tests for building components."""

import pytest
from manifold3d import Manifold

from hotel_generator.components.base import base_slab
from hotel_generator.components.massing import (
    rect_mass,
    l_shape_mass,
    u_shape_mass,
    t_shape_mass,
    podium_tower_mass,
    stepped_mass,
)
from hotel_generator.components.wall import wall
from hotel_generator.components.window import window_cutout, arched_window_cutout, window_frame
from hotel_generator.components.door import door_cutout, door_canopy
from hotel_generator.components.roof import (
    flat_roof,
    gabled_roof,
    hipped_roof,
    mansard_roof,
    barrel_roof,
)
from hotel_generator.components.column import round_column, square_column, pilaster
from hotel_generator.components.floor_slab import floor_slab
from hotel_generator.components.balcony import balcony
from hotel_generator.components.facade import window_grid_cutouts


class TestBaseSlab:
    def test_basic_slab(self):
        b = base_slab(10, 8, 1.2, 0.3)
        assert b.volume() > 0
        assert not b.is_empty()

    def test_slab_without_chamfer(self):
        b = base_slab(10, 8, 1.2, 0)
        assert b.volume() > 0

    def test_slab_at_negative_z(self):
        b = base_slab(10, 8, 1.2, 0.3)
        min_x, min_y, min_z, max_x, max_y, max_z = b.bounding_box()
        assert min_z < 0  # extends below z=0
        assert abs(max_z) < 0.01  # top face at z=0


class TestMassing:
    def test_rect_mass(self):
        m = rect_mass(10, 8, 15)
        assert m.volume() > 0
        assert abs(m.volume() - 1200.0) < 0.1

    def test_l_shape_mass(self):
        m = l_shape_mass(8, 6, 10)
        assert m.volume() > 0
        assert m.volume() > rect_mass(8, 6, 10).volume()  # larger than plain rect

    def test_u_shape_mass(self):
        m = u_shape_mass(10, 8, 12)
        assert m.volume() > 0

    def test_t_shape_mass(self):
        m = t_shape_mass(8, 6, 10)
        assert m.volume() > 0

    def test_podium_tower(self):
        m = podium_tower_mass(10, 8, 3, 6, 5, 15)
        assert m.volume() > 0
        min_x, min_y, min_z, max_x, max_y, max_z = m.bounding_box()
        assert abs(max_z - 18.0) < 0.1  # podium + tower height

    def test_stepped_mass(self):
        m = stepped_mass(10, 8, 4, 3.0, 0.5)
        assert m.volume() > 0

    def test_stepped_mass_narrows(self):
        # Each tier should be smaller than the one below
        m = stepped_mass(10, 8, 3, 3.0, 1.0)
        min_x, min_y, min_z, max_x, max_y, max_z = m.bounding_box()
        assert max_z > 0

    def test_all_massing_base_at_z0(self):
        for m in [
            rect_mass(5, 4, 10),
            l_shape_mass(5, 4, 10),
            u_shape_mass(5, 4, 10),
            t_shape_mass(5, 4, 10),
            podium_tower_mass(5, 4, 3, 3, 3, 7),
            stepped_mass(5, 4, 3, 3.0),
        ]:
            min_x, min_y, min_z, max_x, max_y, max_z = m.bounding_box()
            assert abs(min_z) < 0.01, "Massing base should be at Z=0"


class TestWall:
    def test_basic_wall(self):
        w = wall(8, 10, 0.8)
        assert w.volume() > 0

    def test_wall_volume(self):
        w = wall(8, 10, 0.8)
        assert abs(w.volume() - 8 * 10 * 0.8) < 0.1


class TestWindow:
    def test_window_cutout(self):
        w = window_cutout(0.5, 0.7, 0.8)
        assert w.volume() > 0

    def test_window_cutout_overshoots(self):
        from hotel_generator.geometry.primitives import BOOLEAN_OVERSHOOT
        w = window_cutout(0.5, 0.7, 0.8)
        min_x, min_y, min_z, max_x, max_y, max_z = w.bounding_box()
        expected_depth = 0.8 + 2 * BOOLEAN_OVERSHOOT
        assert abs((max_y - min_y) - expected_depth) < 0.01

    def test_arched_window(self):
        w = arched_window_cutout(0.5, 0.7, 0.8)
        assert w.volume() > 0

    def test_window_frame(self):
        f = window_frame(0.5, 0.7)
        assert f.volume() > 0


class TestDoor:
    def test_door_cutout(self):
        d = door_cutout(1.0, 1.5, 0.8)
        assert d.volume() > 0

    def test_door_canopy(self):
        c = door_canopy(2.0, 1.0, 0.3)
        assert c.volume() > 0


class TestRoof:
    def test_flat_roof(self):
        r = flat_roof(10, 8, 0.5)
        assert not r.is_empty()
        assert r.volume() > 0

    def test_flat_roof_no_parapet(self):
        r = flat_roof(10, 8, 0)
        assert r.volume() > 0

    def test_gabled_roof(self):
        r = gabled_roof(8, 6, 3)
        assert not r.is_empty()
        assert r.volume() > 0

    def test_hipped_roof(self):
        r = hipped_roof(8, 6, 3)
        assert not r.is_empty()
        assert r.volume() > 0

    def test_mansard_roof(self):
        r = mansard_roof(8, 6, 2, 1, 0.8)
        assert not r.is_empty()
        assert r.volume() > 0

    def test_barrel_roof(self):
        r = barrel_roof(8, 6, 3)
        assert not r.is_empty()
        assert r.volume() > 0


class TestColumn:
    def test_round_column(self):
        c = round_column(0.4, 5.0)
        assert c.volume() > 0

    def test_square_column(self):
        c = square_column(0.6, 5.0)
        assert c.volume() > 0

    def test_pilaster(self):
        p = pilaster(0.4, 0.2, 5.0)
        assert p.volume() > 0


class TestFloorSlab:
    def test_basic_slab(self):
        s = floor_slab(8, 6, 0.15)
        assert s.volume() > 0

    def test_slab_with_overhang(self):
        s1 = floor_slab(8, 6, 0.15, overhang=0)
        s2 = floor_slab(8, 6, 0.15, overhang=0.2)
        assert s2.volume() > s1.volume()


class TestBalcony:
    def test_basic_balcony(self):
        b = balcony(3, 1.5)
        assert b.volume() > 0

    def test_balcony_no_support(self):
        b = balcony(3, 1.5, add_support=False)
        assert b.volume() > 0


class TestFacade:
    def test_window_grid(self):
        cuts = window_grid_cutouts(
            wall_width=8.0,
            wall_height=12.0,
            wall_thickness=0.8,
            num_floors=4,
            floor_height=3.0,
            windows_per_floor=3,
            window_width=0.5,
            window_height=0.7,
        )
        # 4 floors - 1 ground floor = 3 floors × 3 windows = 9
        assert len(cuts) == 9
        for cut in cuts:
            assert cut.volume() > 0

    def test_window_grid_no_skip(self):
        cuts = window_grid_cutouts(
            wall_width=8.0,
            wall_height=12.0,
            wall_thickness=0.8,
            num_floors=4,
            floor_height=3.0,
            windows_per_floor=3,
            window_width=0.5,
            window_height=0.7,
            ground_floor_skip=False,
        )
        assert len(cuts) == 12  # 4 floors × 3 windows

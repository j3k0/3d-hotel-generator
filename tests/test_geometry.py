"""Tests for geometry primitives, booleans, and transforms."""

import pytest
from manifold3d import Manifold

from hotel_generator.errors import GeometryError
from hotel_generator.geometry.primitives import (
    box,
    cylinder,
    cone,
    extrude_polygon,
    revolve_profile,
    BOOLEAN_OVERSHOOT,
    BOOLEAN_EMBED,
)
from hotel_generator.geometry.booleans import (
    union_all,
    difference_all,
    compose_disjoint,
)
from hotel_generator.geometry.transforms import (
    translate,
    rotate_z,
    mirror_x,
    mirror_y,
    safe_scale,
)


class TestBox:
    def test_valid_box(self):
        b = box(5, 4, 10)
        assert not b.is_empty()
        assert b.volume() > 0

    def test_box_volume(self):
        b = box(2, 3, 4)
        assert abs(b.volume() - 24.0) < 0.01

    def test_box_centered_xy(self):
        b = box(4, 6, 2)
        min_x, min_y, min_z, max_x, max_y, max_z = b.bounding_box()
        assert abs(min_x - (-2)) < 0.01
        assert abs(max_x - 2) < 0.01
        assert abs(min_y - (-3)) < 0.01
        assert abs(max_y - 3) < 0.01

    def test_box_base_at_z0(self):
        b = box(1, 1, 5)
        min_x, min_y, min_z, max_x, max_y, max_z = b.bounding_box()
        assert abs(min_z) < 0.01
        assert abs(max_z - 5) < 0.01

    def test_zero_width_raises(self):
        with pytest.raises(GeometryError):
            box(0, 1, 1)

    def test_negative_height_raises(self):
        with pytest.raises(GeometryError):
            box(1, 1, -1)


class TestCylinder:
    def test_valid_cylinder(self):
        c = cylinder(1.0, 5.0)
        assert not c.is_empty()
        assert c.volume() > 0

    def test_cylinder_with_segments(self):
        c = cylinder(1.0, 5.0, segments=32)
        assert not c.is_empty()

    def test_zero_radius_raises(self):
        with pytest.raises(GeometryError):
            cylinder(0, 5)

    def test_negative_height_raises(self):
        with pytest.raises(GeometryError):
            cylinder(1, -1)


class TestCone:
    def test_frustum(self):
        c = cone(2.0, 1.0, 5.0)
        assert not c.is_empty()
        assert c.volume() > 0

    def test_pointed_cone(self):
        c = cone(2.0, 0.0, 5.0)
        assert not c.is_empty()

    def test_negative_top_radius_raises(self):
        with pytest.raises(GeometryError):
            cone(2.0, -1.0, 5.0)


class TestExtrude:
    def test_triangle(self):
        pts = [(0, 0), (2, 0), (1, 2)]
        e = extrude_polygon(pts, 3.0)
        assert not e.is_empty()
        assert e.volume() > 0

    def test_rectangle(self):
        pts = [(0, 0), (4, 0), (4, 3), (0, 3)]
        e = extrude_polygon(pts, 2.0)
        assert not e.is_empty()

    def test_too_few_points_raises(self):
        with pytest.raises(GeometryError):
            extrude_polygon([(0, 0), (1, 0)], 1.0)

    def test_zero_height_raises(self):
        with pytest.raises(GeometryError):
            extrude_polygon([(0, 0), (1, 0), (0, 1)], 0)


class TestRevolve:
    def test_dome_profile(self):
        # Simple dome-like profile (rectangle with tapered top)
        pts = [(0, 0), (2, 0), (1.5, 1), (0.5, 1.5), (0, 1.5)]
        r = revolve_profile(pts, segments=16, degrees=360)
        assert not r.is_empty()

    def test_too_few_points_raises(self):
        with pytest.raises(GeometryError):
            revolve_profile([(0, 0), (1, 0)], segments=8)


class TestBooleans:
    def test_union_all_basic(self):
        parts = [box(1, 1, 1), box(2, 2, 2)]
        r = union_all(parts)
        assert not r.is_empty()
        assert r.volume() > 0

    def test_union_all_single(self):
        b = box(3, 3, 3)
        r = union_all([b])
        assert abs(r.volume() - b.volume()) < 0.01

    def test_union_all_empty_list(self):
        r = union_all([])
        assert r.is_empty()

    def test_union_all_filters_empty(self):
        r = union_all([Manifold(), box(1, 1, 1), Manifold()])
        assert not r.is_empty()

    def test_difference_all(self):
        base = box(10, 10, 10)
        cuts = [box(2, 2, 20)]  # through-cut
        r = difference_all(base, cuts)
        assert not r.is_empty()
        assert r.volume() < base.volume()

    def test_difference_empty_base_raises(self):
        with pytest.raises(GeometryError):
            difference_all(Manifold(), [box(1, 1, 1)])

    def test_difference_no_cutouts(self):
        base = box(5, 5, 5)
        r = difference_all(base, [])
        assert abs(r.volume() - base.volume()) < 0.01

    def test_compose_disjoint(self):
        a = box(1, 1, 1).translate([0, 0, 0])
        b = box(1, 1, 1).translate([5, 0, 0])
        r = compose_disjoint([a, b])
        assert not r.is_empty()

    def test_compose_empty_list(self):
        r = compose_disjoint([])
        assert r.is_empty()


class TestTransforms:
    def test_translate(self):
        b = box(1, 1, 1)
        t = translate(b, 10, 20, 30)
        min_x, min_y, min_z, max_x, max_y, max_z = t.bounding_box()
        assert abs(min_x - 9.5) < 0.01
        assert abs(min_y - 19.5) < 0.01
        assert abs(min_z - 30) < 0.01

    def test_rotate_z(self):
        b = box(2, 1, 1)
        r = rotate_z(b, 90)
        assert not r.is_empty()
        assert abs(r.volume() - b.volume()) < 0.01

    def test_mirror_x(self):
        b = box(2, 1, 1).translate([5, 0, 0])
        m = mirror_x(b)
        min_x, min_y, min_z, max_x, max_y, max_z = m.bounding_box()
        assert max_x < 0  # mirrored to negative X

    def test_mirror_y(self):
        b = box(1, 2, 1).translate([0, 5, 0])
        m = mirror_y(b)
        min_x, min_y, min_z, max_x, max_y, max_z = m.bounding_box()
        assert max_y < 0

    def test_safe_scale(self):
        b = box(1, 1, 1)
        s = safe_scale(b, 2, 2, 2)
        assert not s.is_empty()
        assert abs(s.volume() - 8.0) < 0.01

    def test_safe_scale_non_uniform(self):
        b = box(1, 1, 1)
        s = safe_scale(b, 2, 3, 4)
        assert abs(s.volume() - 24.0) < 0.01


class TestConstants:
    def test_overshoot_positive(self):
        assert BOOLEAN_OVERSHOOT > 0

    def test_embed_positive(self):
        assert BOOLEAN_EMBED > 0

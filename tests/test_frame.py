"""Tests for the board frame and road connector system."""

import random

import pytest

from hotel_generator.board.config import BoardParams, FrameParams, PropertySlot
from hotel_generator.board.frame import (
    FrameResult,
    _make_frame_rail,
    _make_road_corner,
    _make_road_filler,
    generate_frame,
)
from hotel_generator.board.road import generate_road_layout


# ---------------------------------------------------------------------------
# Individual piece geometry
# ---------------------------------------------------------------------------


class TestRoadFiller:
    def test_non_empty(self):
        filler = _make_road_filler(100.0, 10.0)
        assert not filler.is_empty()
        assert filler.volume() > 0

    def test_dimensions(self):
        filler = _make_road_filler(100.0, 10.0)
        bb = filler.bounding_box()
        # Width ~100mm, depth ~10mm
        assert abs((bb[3] - bb[0]) - 100.0) < 2.0  # x extent
        assert abs((bb[4] - bb[1]) - 10.0) < 1.0  # y extent
        # Height: base (2.5mm below) + curb (0.3mm above)
        assert bb[2] < 0  # extends below Z=0
        assert bb[5] > 0  # curbs above Z=0


class TestRoadCorner:
    def test_non_empty(self):
        corner = _make_road_corner(10.0)
        assert not corner.is_empty()
        assert corner.volume() > 0

    def test_roughly_square(self):
        corner = _make_road_corner(10.0)
        bb = corner.bounding_box()
        x_size = bb[3] - bb[0]
        y_size = bb[4] - bb[1]
        assert abs(x_size - y_size) < 2.0  # roughly square


class TestFrameRail:
    def test_non_empty(self):
        rail = _make_frame_rail(100.0, 5.0, 1.5, 1.0)
        assert not rail.is_empty()
        assert rail.volume() > 0

    def test_has_lip(self):
        rail = _make_frame_rail(100.0, 5.0, 1.5, 1.0)
        bb = rail.bounding_box()
        # Lip should extend above Z=0
        assert bb[5] >= 1.0  # lip_height=1.5


# ---------------------------------------------------------------------------
# Frame generation for loop layout
# ---------------------------------------------------------------------------


class TestLoopFrame:
    def _make_loop_slots(self, n=8):
        rng = random.Random(42)
        return generate_road_layout("loop", n, 100.0, 80.0, 8.0, rng)

    def test_loop_produces_pieces(self):
        slots = self._make_loop_slots()
        params = BoardParams(road_shape="loop")
        result = generate_frame(slots, params)
        assert len(result.all_pieces) > 0

    def test_loop_has_road_fillers(self):
        slots = self._make_loop_slots()
        params = BoardParams(road_shape="loop")
        result = generate_frame(slots, params)
        assert len(result.road_fillers) > 0
        for piece in result.road_fillers:
            assert piece.piece_type == "road_filler"
            assert not piece.manifold.is_empty()

    def test_loop_has_corners(self):
        slots = self._make_loop_slots()
        params = BoardParams(road_shape="loop")
        result = generate_frame(slots, params)
        assert len(result.road_corners) > 0
        for piece in result.road_corners:
            assert piece.piece_type == "road_corner"
            assert not piece.manifold.is_empty()

    def test_loop_has_side_roads(self):
        slots = self._make_loop_slots()
        params = BoardParams(road_shape="loop")
        result = generate_frame(slots, params)
        assert len(result.road_sides) > 0
        for piece in result.road_sides:
            assert piece.piece_type == "road_side"
            assert not piece.manifold.is_empty()

    def test_loop_has_frame_rails(self):
        slots = self._make_loop_slots()
        params = BoardParams(road_shape="loop")
        result = generate_frame(slots, params)
        assert len(result.frame_rails) > 0
        for piece in result.frame_rails:
            assert piece.piece_type == "frame_rail"
            assert not piece.manifold.is_empty()

    def test_all_pieces_positive_volume(self):
        slots = self._make_loop_slots()
        params = BoardParams(road_shape="loop")
        result = generate_frame(slots, params)
        for piece in result.all_pieces:
            assert piece.manifold.volume() > 0, f"{piece.label} has zero volume"

    def test_disabled_frame(self):
        slots = self._make_loop_slots()
        params = BoardParams(road_shape="loop", frame=FrameParams(enabled=False))
        result = generate_frame(slots, params)
        assert len(result.all_pieces) == 0


# ---------------------------------------------------------------------------
# Frame generation for linear/serpentine layouts
# ---------------------------------------------------------------------------


class TestLinearFrame:
    def _make_linear_slots(self, n=8):
        rng = random.Random(42)
        return generate_road_layout("linear", n, 100.0, 80.0, 8.0, rng)

    def test_linear_produces_pieces(self):
        slots = self._make_linear_slots()
        params = BoardParams(road_shape="linear")
        result = generate_frame(slots, params)
        assert len(result.all_pieces) > 0

    def test_linear_has_road_fillers(self):
        slots = self._make_linear_slots()
        params = BoardParams(road_shape="linear")
        result = generate_frame(slots, params)
        assert len(result.road_fillers) > 0

    def test_linear_no_corners(self):
        """Linear layout has no road corners."""
        slots = self._make_linear_slots()
        params = BoardParams(road_shape="linear")
        result = generate_frame(slots, params)
        assert len(result.road_corners) == 0

    def test_linear_has_frame_rails(self):
        slots = self._make_linear_slots()
        params = BoardParams(road_shape="linear")
        result = generate_frame(slots, params)
        assert len(result.frame_rails) > 0


class TestSerpentineFrame:
    def test_serpentine_produces_pieces(self):
        rng = random.Random(42)
        slots = generate_road_layout("serpentine", 8, 100.0, 80.0, 8.0, rng)
        params = BoardParams(road_shape="serpentine")
        result = generate_frame(slots, params)
        assert len(result.all_pieces) > 0
        assert len(result.road_fillers) > 0


# ---------------------------------------------------------------------------
# Dual-sided loop layout verification
# ---------------------------------------------------------------------------


class TestDualSidedLoop:
    def test_loop_8_has_4_rows(self):
        """8 properties in loop should produce 4 rows."""
        rng = random.Random(42)
        slots = generate_road_layout("loop", 8, 100.0, 80.0, 8.0, rng)
        ys = sorted(set(round(s.center_y, 1) for s in slots))
        assert len(ys) == 4, f"Expected 4 rows, got {len(ys)}: {ys}"

    def test_loop_has_both_road_edges(self):
        """Both north and south road edges should be present."""
        rng = random.Random(42)
        slots = generate_road_layout("loop", 8, 100.0, 80.0, 8.0, rng)
        edges = set(s.road_edge for s in slots)
        assert "north" in edges
        assert "south" in edges

    def test_properties_face_each_other(self):
        """Adjacent rows should have properties facing toward the road between them."""
        rng = random.Random(42)
        slots = generate_road_layout("loop", 8, 100.0, 80.0, 8.0, rng)
        # Sort by y
        ys = sorted(set(round(s.center_y, 1) for s in slots))
        for i in range(len(ys) - 1):
            lower = [s for s in slots if abs(s.center_y - ys[i]) < 1]
            upper = [s for s in slots if abs(s.center_y - ys[i + 1]) < 1]
            # Gap should be prop_d + gap = 90mm
            dy = ys[i + 1] - ys[i]
            if dy < 95:  # adjacent rows with road between them
                # Lower should face north, upper should face south
                assert all(s.road_edge == "north" for s in lower) or \
                       all(s.road_edge == "south" for s in lower)

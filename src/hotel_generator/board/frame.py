"""Board frame and road connector geometry.

Generates three types of pieces for a 3D-printable game board:
1. Road fillers: fill the gaps between facing property plates with road surface
2. Road side strips: vertical road segments connecting top/bottom roads (loop)
3. Road corners: 90-degree turn pieces at road intersections (loop)
4. Frame rails: outer border rails with retaining lip
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from manifold3d import Manifold

from hotel_generator.board.config import BoardParams, FrameParams, PropertySlot
from hotel_generator.geometry.booleans import compose_disjoint, difference_all, union_all
from hotel_generator.geometry.primitives import box, cylinder
from hotel_generator.geometry.transforms import rotate_z, translate


# Road geometry constants (match property_builder._make_road_strip)
ROAD_RECESS = 0.2  # mm below Z=0
CURB_HEIGHT = 0.3  # mm above Z=0
CURB_WIDTH = 0.8  # mm wide
BASE_THICKNESS = 2.5  # mm (property plate base thickness)


@dataclass
class FramePiece:
    """A single frame or road connector piece."""

    manifold: Manifold
    piece_type: str  # "road_filler", "road_side", "road_corner", "frame_rail"
    label: str  # e.g. "road_filler_01", "corner_sw", "rail_01"
    x: float  # Position in board coordinates
    y: float
    rotation: float = 0.0  # Degrees around Z


@dataclass
class FrameResult:
    """All frame pieces for a board."""

    road_fillers: list[FramePiece] = field(default_factory=list)
    road_sides: list[FramePiece] = field(default_factory=list)
    road_corners: list[FramePiece] = field(default_factory=list)
    frame_rails: list[FramePiece] = field(default_factory=list)

    @property
    def all_pieces(self) -> list[FramePiece]:
        return self.road_fillers + self.road_sides + self.road_corners + self.frame_rails


# ---------------------------------------------------------------------------
# Road filler geometry
# ---------------------------------------------------------------------------

def _make_road_filler(width: float, gap: float) -> Manifold:
    """Create a road segment filling the gap between two facing properties.

    Matches the road surface/curb style from property_builder._make_road_strip.
    Centered on X/Y, base at Z=-BASE_THICKNESS, road surface at Z=0.
    """
    # Base slab
    slab = box(width, gap, BASE_THICKNESS)
    slab = translate(slab, z=-BASE_THICKNESS)

    # Road recess (subtract from top surface)
    recess = box(width - 1.0, gap - 2 * CURB_WIDTH, ROAD_RECESS + 0.1)
    recess = translate(recess, z=-ROAD_RECESS)
    slab = difference_all(slab, [recess])

    # Curb lines along both edges
    curb_near = box(width - 1.0, CURB_WIDTH, CURB_HEIGHT)
    curb_near = translate(curb_near, y=-(gap / 2 - CURB_WIDTH / 2))
    curb_far = box(width - 1.0, CURB_WIDTH, CURB_HEIGHT)
    curb_far = translate(curb_far, y=(gap / 2 - CURB_WIDTH / 2))

    return union_all([slab, curb_near, curb_far])


# ---------------------------------------------------------------------------
# Road corner geometry
# ---------------------------------------------------------------------------

def _make_road_corner(gap: float) -> Manifold:
    """Create a 90-degree road corner piece.

    Square piece at a road intersection. Centered on X/Y.
    """
    # Base slab
    slab = box(gap, gap, BASE_THICKNESS)
    slab = translate(slab, z=-BASE_THICKNESS)

    # Recess the road surface (center area)
    inner_size = gap - 2 * CURB_WIDTH
    if inner_size > 0:
        recess = box(inner_size, inner_size, ROAD_RECESS + 0.1)
        recess = translate(recess, z=-ROAD_RECESS)
        slab = difference_all(slab, [recess])

    # Corner curbs: short segments along each edge
    parts = [slab]
    # Curb along -Y edge (bottom)
    cb = box(gap - 2 * CURB_WIDTH, CURB_WIDTH, CURB_HEIGHT)
    cb = translate(cb, y=-(gap / 2 - CURB_WIDTH / 2))
    parts.append(cb)
    # Curb along +Y edge (top)
    ct = box(gap - 2 * CURB_WIDTH, CURB_WIDTH, CURB_HEIGHT)
    ct = translate(ct, y=(gap / 2 - CURB_WIDTH / 2))
    parts.append(ct)
    # Curb along -X edge (left)
    cl = box(CURB_WIDTH, gap - 2 * CURB_WIDTH, CURB_HEIGHT)
    cl = translate(cl, x=-(gap / 2 - CURB_WIDTH / 2))
    parts.append(cl)
    # Curb along +X edge (right)
    cr = box(CURB_WIDTH, gap - 2 * CURB_WIDTH, CURB_HEIGHT)
    cr = translate(cr, x=(gap / 2 - CURB_WIDTH / 2))
    parts.append(cr)

    return union_all(parts)


# ---------------------------------------------------------------------------
# Frame rail geometry
# ---------------------------------------------------------------------------

def _make_frame_rail(
    length: float,
    rail_width: float,
    lip_height: float,
    lip_thickness: float,
) -> Manifold:
    """Create an outer frame rail with retaining lip.

    Centered on X, extends in +Y direction from inner edge.
    Base at Z=-BASE_THICKNESS, lip extends above Z=0.
    """
    # Base rail (flush with property plate bottom)
    base = box(length, rail_width, BASE_THICKNESS)
    base = translate(base, z=-BASE_THICKNESS)

    # Lip along outer edge (retains property plate)
    lip = box(length, lip_thickness, lip_height)
    lip = translate(lip, y=(rail_width / 2 - lip_thickness / 2))

    return union_all([base, lip])


# ---------------------------------------------------------------------------
# Frame generation (main entry point)
# ---------------------------------------------------------------------------

def generate_frame(
    slots: list[PropertySlot],
    board_params: BoardParams,
) -> FrameResult:
    """Generate all frame and road connector pieces for a board layout."""
    if not board_params.frame.enabled:
        return FrameResult()

    road_shape = board_params.road_shape
    prop_w = board_params.property_width
    prop_d = board_params.property_depth
    road_w = board_params.road_width
    gap = road_w + 2.0
    frame = board_params.frame

    if road_shape == "loop":
        return _generate_loop_frame(slots, prop_w, prop_d, gap, frame)
    elif road_shape in ("serpentine", "linear"):
        return _generate_linear_frame(slots, prop_w, prop_d, gap, frame)
    else:
        return FrameResult()


def _generate_loop_frame(
    slots: list[PropertySlot],
    prop_w: float,
    prop_d: float,
    gap: float,
    frame_params: FrameParams,
) -> FrameResult:
    """Generate frame for the dual-sided loop layout.

    The loop layout has 4 rows (outer_bottom, inner_bottom, inner_top, outer_top)
    with horizontal roads between outer/inner pairs and side roads connecting them.
    """
    result = FrameResult()

    if len(slots) < 3:
        return result

    # Group slots by row based on Y coordinate
    rows = _group_slots_by_row(slots)
    if len(rows) < 2:
        return result

    sorted_row_ys = sorted(rows.keys())

    # --- Road fillers between adjacent rows ---
    # Roads exist between pairs of rows where properties face each other
    filler_idx = 1
    for i in range(len(sorted_row_ys) - 1):
        y_lower = sorted_row_ys[i]
        y_upper = sorted_row_ys[i + 1]
        lower_slots = rows[y_lower]
        upper_slots = rows[y_upper]

        # Check if these rows face each other (road between them)
        lower_face_up = any(s.road_edge in ("north",) for s in lower_slots)
        upper_face_down = any(s.road_edge in ("south",) for s in upper_slots)

        if not (lower_face_up or upper_face_down):
            continue

        # Road center Y
        road_y = (y_lower + prop_d / 2 + y_upper - prop_d / 2) / 2

        # Compute road filler width and positions
        all_xs = sorted(set(s.center_x for s in lower_slots + upper_slots))
        for x in all_xs:
            filler = _make_road_filler(prop_w, gap)
            filler = translate(filler, x=x, y=road_y)
            result.road_fillers.append(FramePiece(
                manifold=filler,
                piece_type="road_filler",
                label=f"road_filler_{filler_idx:02d}",
                x=x, y=road_y,
            ))
            filler_idx += 1

    # --- Side road strips (left and right) ---
    # Connect horizontal roads vertically on both sides
    if len(sorted_row_ys) >= 4:
        # Find the road Y positions
        road_ys = []
        for i in range(len(sorted_row_ys) - 1):
            y_lower = sorted_row_ys[i]
            y_upper = sorted_row_ys[i + 1]
            road_y = (y_lower + prop_d / 2 + y_upper - prop_d / 2) / 2
            road_ys.append(road_y)

        # Left side: x = leftmost property edge - gap/2
        all_xs = sorted(set(s.center_x for s in slots))
        left_x = all_xs[0] - prop_w / 2 - gap / 2
        right_x = all_xs[-1] + prop_w / 2 + gap / 2

        # Side road between each pair of horizontal roads
        side_idx = 1
        for i in range(len(road_ys) - 1):
            y_bottom_road = road_ys[i]
            y_top_road = road_ys[i + 1]
            side_length = y_top_road - y_bottom_road
            side_center_y = (y_bottom_road + y_top_road) / 2

            if side_length <= gap:
                continue

            for side_x in [left_x, right_x]:
                # Road filler rotated 90 degrees (width=side_length, running vertically)
                side_road = _make_road_filler(side_length, gap)
                side_road = rotate_z(side_road, 90)
                side_road = translate(side_road, x=side_x, y=side_center_y)
                result.road_sides.append(FramePiece(
                    manifold=side_road,
                    piece_type="road_side",
                    label=f"road_side_{side_idx:02d}",
                    x=side_x, y=side_center_y,
                    rotation=90,
                ))
                side_idx += 1

        # --- Road corners ---
        # At each intersection of horizontal and vertical roads
        corner_idx = 1
        for road_y in road_ys:
            for side_x in [left_x, right_x]:
                corner = _make_road_corner(gap)
                corner = translate(corner, x=side_x, y=road_y)
                label = f"road_corner_{corner_idx:02d}"
                result.road_corners.append(FramePiece(
                    manifold=corner,
                    piece_type="road_corner",
                    label=label,
                    x=side_x, y=road_y,
                ))
                corner_idx += 1

    # --- Outer frame rails ---
    _add_outer_rails(result, slots, prop_w, prop_d, gap, frame_params)

    return result


def _generate_linear_frame(
    slots: list[PropertySlot],
    prop_w: float,
    prop_d: float,
    gap: float,
    frame_params: FrameParams,
) -> FrameResult:
    """Generate frame for serpentine/linear layouts (two parallel rows)."""
    result = FrameResult()

    if len(slots) < 2:
        return result

    # Group into top and bottom rows
    rows = _group_slots_by_row(slots)
    if len(rows) < 2:
        return result

    sorted_row_ys = sorted(rows.keys())

    # Road fillers between the two rows
    y_lower = sorted_row_ys[0]
    y_upper = sorted_row_ys[-1]
    road_y = (y_lower + prop_d / 2 + y_upper - prop_d / 2) / 2

    all_xs = sorted(set(s.center_x for s in slots))
    filler_idx = 1
    for x in all_xs:
        filler = _make_road_filler(prop_w, gap)
        filler = translate(filler, x=x, y=road_y)
        result.road_fillers.append(FramePiece(
            manifold=filler,
            piece_type="road_filler",
            label=f"road_filler_{filler_idx:02d}",
            x=x, y=road_y,
        ))
        filler_idx += 1

    # Outer frame rails
    _add_outer_rails(result, slots, prop_w, prop_d, gap, frame_params)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _group_slots_by_row(
    slots: list[PropertySlot],
    tolerance: float = 5.0,
) -> dict[float, list[PropertySlot]]:
    """Group property slots into rows by Y coordinate."""
    rows: dict[float, list[PropertySlot]] = {}
    for slot in slots:
        matched = False
        for y_key in rows:
            if abs(slot.center_y - y_key) < tolerance:
                rows[y_key].append(slot)
                matched = True
                break
        if not matched:
            rows[slot.center_y] = [slot]
    return rows


def _add_outer_rails(
    result: FrameResult,
    slots: list[PropertySlot],
    prop_w: float,
    prop_d: float,
    gap: float,
    frame_params: FrameParams,
) -> None:
    """Add outer frame rails around the board perimeter."""
    rail_w = frame_params.frame_width
    lip_h = frame_params.lip_height
    lip_t = frame_params.lip_thickness

    # Find board extents
    rows = _group_slots_by_row(slots)
    sorted_row_ys = sorted(rows.keys())
    all_xs = sorted(set(s.center_x for s in slots))

    if not sorted_row_ys or not all_xs:
        return

    # Bottom edge rail (below bottommost row)
    bottom_y = sorted_row_ys[0] - prop_d / 2
    bottom_slots = rows[sorted_row_ys[0]]
    # Only add rail if these properties face north (road is above, outer edge is below)
    if any(s.road_edge == "north" for s in bottom_slots):
        total_w = (all_xs[-1] - all_xs[0]) + prop_w
        rail = _make_frame_rail(total_w, rail_w, lip_h, lip_t)
        # Rotate so lip faces outward (south)
        rail = rotate_z(rail, 180)
        rail_y = bottom_y - rail_w / 2
        rail_x = (all_xs[0] + all_xs[-1]) / 2
        rail = translate(rail, x=rail_x, y=rail_y)
        result.frame_rails.append(FramePiece(
            manifold=rail, piece_type="frame_rail",
            label="rail_bottom", x=rail_x, y=rail_y, rotation=180,
        ))

    # Top edge rail (above topmost row)
    top_y = sorted_row_ys[-1] + prop_d / 2
    top_slots = rows[sorted_row_ys[-1]]
    if any(s.road_edge == "south" for s in top_slots):
        total_w = (all_xs[-1] - all_xs[0]) + prop_w
        rail = _make_frame_rail(total_w, rail_w, lip_h, lip_t)
        rail_y = top_y + rail_w / 2
        rail_x = (all_xs[0] + all_xs[-1]) / 2
        rail = translate(rail, x=rail_x, y=rail_y)
        result.frame_rails.append(FramePiece(
            manifold=rail, piece_type="frame_rail",
            label="rail_top", x=rail_x, y=rail_y,
        ))

    # Left edge rail
    left_x = all_xs[0] - prop_w / 2
    total_h = (sorted_row_ys[-1] - sorted_row_ys[0]) + prop_d
    rail = _make_frame_rail(total_h, rail_w, lip_h, lip_t)
    rail = rotate_z(rail, 90)
    rail_x_pos = left_x - rail_w / 2
    rail_y_pos = (sorted_row_ys[0] + sorted_row_ys[-1]) / 2
    rail = translate(rail, x=rail_x_pos, y=rail_y_pos)
    result.frame_rails.append(FramePiece(
        manifold=rail, piece_type="frame_rail",
        label="rail_left", x=rail_x_pos, y=rail_y_pos, rotation=90,
    ))

    # Right edge rail
    right_x = all_xs[-1] + prop_w / 2
    rail = _make_frame_rail(total_h, rail_w, lip_h, lip_t)
    rail = rotate_z(rail, -90)
    rail_x_pos = right_x + rail_w / 2
    rail = translate(rail, x=rail_x_pos, y=rail_y_pos)
    result.frame_rails.append(FramePiece(
        manifold=rail, piece_type="frame_rail",
        label="rail_right", x=rail_x_pos, y=rail_y_pos, rotation=-90,
    ))

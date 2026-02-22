"""Road generation: creates property slots along a procedural road layout.

Three road shapes are supported:
- loop: properties around a rectangular loop
- serpentine: properties on alternating sides of an S-curve
- linear: properties on both sides of a straight road
"""

from __future__ import annotations

import random

from hotel_generator.board.config import DEFAULT_PRESET_ASSIGNMENTS, PropertySlot
from hotel_generator.errors import InvalidParamsError


def generate_road_layout(
    road_shape: str,
    num_properties: int,
    property_width: float,
    property_depth: float,
    road_width: float,
    rng: random.Random,
    style_assignments: dict[int, str] | None = None,
) -> list[PropertySlot]:
    """Generate property slots along a road.

    Args:
        road_shape: One of "loop", "serpentine", "linear".
        num_properties: Number of properties (1-12).
        property_width: Width of each property plate (mm).
        property_depth: Depth of each property plate (mm).
        road_width: Width of the road (mm).
        rng: Seeded random generator.
        style_assignments: Optional map of index → preset name.

    Returns:
        List of PropertySlot objects with positions and preset assignments.
    """
    if road_shape == "loop":
        slots = _loop_layout(num_properties, property_width, property_depth, road_width)
    elif road_shape == "serpentine":
        slots = _serpentine_layout(num_properties, property_width, property_depth, road_width)
    elif road_shape == "linear":
        slots = _linear_layout(num_properties, property_width, property_depth, road_width)
    else:
        raise InvalidParamsError(f"Unknown road_shape: {road_shape}")

    # Assign presets
    presets = list(DEFAULT_PRESET_ASSIGNMENTS)
    for i, slot in enumerate(slots):
        if style_assignments and i in style_assignments:
            slot.assigned_preset = style_assignments[i]
        elif i < len(presets):
            slot.assigned_preset = presets[i]
        else:
            # Wrap around if more properties than presets
            slot.assigned_preset = presets[i % len(presets)]

    return slots


def _loop_layout(
    num_properties: int,
    prop_w: float,
    prop_d: float,
    road_w: float,
) -> list[PropertySlot]:
    """Properties on both sides of a rectangular loop road (boulevard style).

    Layout (for 8 properties, 2 per quadrant):
           [P6] [P7]          ← outer top, road_edge=south
            ═════════          ← top road
           [P5] [P4]          ← inner top, road_edge=north
                               ← center gap
           [P2] [P3]          ← inner bottom, road_edge=south
            ═════════          ← bottom road
           [P0] [P1]          ← outer bottom, road_edge=north

    Left and right road segments connect the top and bottom roads
    to form a loop. Properties face inward toward the road on
    both the outer and inner sides.
    """
    slots: list[PropertySlot] = []
    gap = road_w + 2.0  # spacing between facing property edges

    if num_properties <= 2:
        # Just two properties facing each other
        for i in range(num_properties):
            side = -1 if i == 0 else 1
            slots.append(PropertySlot(
                index=i,
                center_x=0,
                center_y=side * (prop_d / 2 + gap / 2),
                road_edge="north" if side < 0 else "south",
                assigned_preset="",
            ))
        return slots

    # Split into outer and inner rings
    outer_count = (num_properties + 1) // 2
    inner_count = num_properties - outer_count

    # Distribute outer across bottom and top
    outer_bottom = (outer_count + 1) // 2
    outer_top = outer_count - outer_bottom

    # Distribute inner across bottom and top
    inner_bottom = (inner_count + 1) // 2
    inner_top = inner_count - inner_bottom

    # Compute columns count (max properties in any row)
    cols = max(outer_bottom, outer_top, inner_bottom, inner_top, 1)
    row_width = cols * (prop_w + 2.0)

    # Vertical positions (centered at y=0):
    # From bottom to top:
    #   outer_bottom: road_edge="north" (faces up toward bottom road)
    #   --- bottom road gap ---
    #   inner_bottom: road_edge="south" (faces down toward bottom road)
    #   --- center gap between inner rows ---
    #   inner_top:    road_edge="north" (faces up toward top road)
    #   --- top road gap ---
    #   outer_top:    road_edge="south" (faces down toward top road)

    center_gap = gap  # gap between inner bottom and inner top rows
    total_height = 4 * prop_d + 2 * gap + center_gap

    # Y-coordinates of row centers (from bottom to top)
    y_outer_bottom = -total_height / 2 + prop_d / 2
    y_inner_bottom = y_outer_bottom + prop_d + gap
    y_inner_top = y_inner_bottom + prop_d + center_gap
    y_outer_top = y_inner_top + prop_d + gap

    idx = 0

    # Row helper: place properties evenly across a row
    def _place_row(count, y, road_edge):
        nonlocal idx
        for j in range(count):
            x = -row_width / 2 + (j + 0.5) * (row_width / max(count, 1))
            slots.append(PropertySlot(idx, x, y, road_edge, ""))
            idx += 1

    # Outer bottom (face north → road above)
    _place_row(outer_bottom, y_outer_bottom, "north")

    # Inner bottom (face south → road below)
    _place_row(inner_bottom, y_inner_bottom, "south")

    # Inner top (face north → road above)
    _place_row(inner_top, y_inner_top, "north")

    # Outer top (face south → road below)
    _place_row(outer_top, y_outer_top, "south")

    return slots


def _serpentine_layout(
    num_properties: int,
    prop_w: float,
    prop_d: float,
    road_w: float,
) -> list[PropertySlot]:
    """Properties on alternating sides of a serpentine road.

    [P0] [P1] [P2] [P3]
    ════════════════════╗
    [P7] [P6] [P5] [P4]║
    ╔═══════════════════╝
    """
    slots: list[PropertySlot] = []
    half = (num_properties + 1) // 2
    gap = road_w + 2.0

    for i in range(num_properties):
        if i < half:
            # Top row (facing south)
            x = i * (prop_w + 2.0)
            y = gap / 2 + prop_d / 2
            edge = "south"
        else:
            # Bottom row (facing north), reversed order
            j = num_properties - 1 - i
            x = j * (prop_w + 2.0)
            y = -(gap / 2 + prop_d / 2)
            edge = "north"
        slots.append(PropertySlot(i, x, y, edge, ""))

    # Center the layout
    if slots:
        cx = sum(s.center_x for s in slots) / len(slots)
        for s in slots:
            s.center_x -= cx

    return slots


def _linear_layout(
    num_properties: int,
    prop_w: float,
    prop_d: float,
    road_w: float,
) -> list[PropertySlot]:
    """Properties on both sides of a straight road.

    [P0] [P2] [P4] [P6]
    ════════════════════
    [P1] [P3] [P5] [P7]
    """
    slots: list[PropertySlot] = []
    gap = road_w + 2.0
    cols = (num_properties + 1) // 2

    for i in range(num_properties):
        col = i // 2
        side = 1 if i % 2 == 0 else -1  # even=top, odd=bottom
        x = col * (prop_w + 2.0)
        y = side * (gap / 2 + prop_d / 2)
        edge = "south" if side > 0 else "north"
        slots.append(PropertySlot(i, x, y, edge, ""))

    # Center the layout
    if slots:
        cx = sum(s.center_x for s in slots) / len(slots)
        for s in slots:
            s.center_x -= cx

    return slots


def _distribute_sides(n: int) -> tuple[int, int, int, int]:
    """Distribute n properties across 4 sides of a rectangle.

    Returns (bottom, left, top, right) counts.
    """
    if n <= 4:
        # One per side
        counts = [0, 0, 0, 0]
        for i in range(n):
            counts[i % 4] = 1
        return tuple(counts)  # type: ignore[return-value]

    # Aim for roughly equal on long sides (bottom/top), fewer on short sides
    long_total = n * 2 // 3
    short_total = n - long_total
    bottom = (long_total + 1) // 2
    top = long_total - bottom
    left = (short_total + 1) // 2
    right = short_total - left
    return (bottom, left, top, right)

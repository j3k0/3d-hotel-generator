"""Building footprint geometry and overlap detection."""

from __future__ import annotations

import math
from dataclasses import dataclass

from hotel_generator.config import BuildingPlacement


@dataclass
class BuildingFootprint:
    """Axis-aligned bounding box of a placed building."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_y - self.min_y

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2


def placement_footprint(p: BuildingPlacement) -> BuildingFootprint:
    """Compute the AABB footprint for a placed building.

    Handles 0/90/180/270 degree rotations by swapping width/depth.
    """
    rot = p.rotation % 360
    if rot in (90, 270):
        half_w = p.depth / 2
        half_d = p.width / 2
    else:
        half_w = p.width / 2
        half_d = p.depth / 2
    return BuildingFootprint(
        min_x=p.x - half_w,
        min_y=p.y - half_d,
        max_x=p.x + half_w,
        max_y=p.y + half_d,
    )


def footprints_overlap(a: BuildingFootprint, b: BuildingFootprint, margin: float = 0.0) -> bool:
    """Check if two footprints overlap (with optional margin)."""
    return not (
        a.max_x + margin <= b.min_x
        or b.max_x + margin <= a.min_x
        or a.max_y + margin <= b.min_y
        or b.max_y + margin <= a.min_y
    )


def any_overlaps(placements: list[BuildingPlacement], margin: float = 0.0) -> bool:
    """Check if any placements overlap each other."""
    footprints = [placement_footprint(p) for p in placements]
    for i in range(len(footprints)):
        for j in range(i + 1, len(footprints)):
            if footprints_overlap(footprints[i], footprints[j], margin):
                return True
    return False


def compute_lot_bounds(placements: list[BuildingPlacement], margin: float = 2.0) -> tuple[float, float]:
    """Compute the lot size needed to contain all placements.

    Returns (lot_width, lot_depth) with margin around all buildings.
    """
    if not placements:
        return (0.0, 0.0)
    footprints = [placement_footprint(p) for p in placements]
    min_x = min(f.min_x for f in footprints) - margin
    min_y = min(f.min_y for f in footprints) - margin
    max_x = max(f.max_x for f in footprints) + margin
    max_y = max(f.max_y for f in footprints) + margin
    return (max_x - min_x, max_y - min_y)


def footprints_fit_lot(
    placements: list[BuildingPlacement],
    lot_width: float,
    lot_depth: float,
) -> bool:
    """Check if all placements fit within the given lot size."""
    needed_w, needed_d = compute_lot_bounds(placements, margin=0.0)
    return needed_w <= lot_width and needed_d <= lot_depth

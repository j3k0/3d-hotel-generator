"""Landscape components for garden/leisure areas.

Provides trees, hedges, swimming pools, paths, and terraces that can
be placed on property base plates. All geometry follows the standard
conventions: centered on X/Y, base at Z=0, returns Manifold.
"""

from __future__ import annotations

import math
import random

from manifold3d import Manifold

from hotel_generator.errors import GeometryError
from hotel_generator.geometry.booleans import compose_disjoint, union_all
from hotel_generator.geometry.primitives import (
    BOOLEAN_EMBED,
    BOOLEAN_OVERSHOOT,
    box,
    cone,
    cylinder,
    extrude_polygon,
)
from hotel_generator.geometry.transforms import translate, rotate_z, safe_scale


# ---------------------------------------------------------------------------
# Trees
# ---------------------------------------------------------------------------

def deciduous_tree(
    height: float = 4.0,
    canopy_radius: float = 1.5,
    trunk_radius: float = 0.4,
    rng: random.Random | None = None,
) -> Manifold:
    """Deciduous tree: cylindrical trunk + sphere-like canopy.

    Args:
        height: Total tree height (mm). Trunk is ~40% of height.
        canopy_radius: Radius of the spherical canopy (mm).
        trunk_radius: Radius of the trunk cylinder (mm).
        rng: Optional RNG for slight variation in proportions.
    """
    if rng is not None:
        height *= rng.uniform(0.85, 1.15)
        canopy_radius *= rng.uniform(0.9, 1.1)

    trunk_height = height * 0.45
    canopy_height = height - trunk_height + BOOLEAN_EMBED

    trunk = cylinder(trunk_radius, trunk_height)

    # Sphere-like canopy: use a short wide cylinder scaled into an oblate sphere.
    # More robust than revolve_profile for small radii.
    canopy_base = cylinder(canopy_radius, canopy_radius * 2.0, segments=12)
    # Scale Z to make it sphere-ish (flattened top/bottom)
    canopy = safe_scale(canopy_base, sx=1.0, sy=1.0, sz=0.7)
    canopy = translate(canopy, z=trunk_height - BOOLEAN_EMBED)

    return union_all([trunk, canopy])


def conifer_tree(
    height: float = 5.0,
    canopy_radius: float = 1.2,
    trunk_radius: float = 0.4,
    rng: random.Random | None = None,
) -> Manifold:
    """Conifer tree: cylindrical trunk + cone canopy.

    Args:
        height: Total tree height (mm).
        canopy_radius: Base radius of the cone canopy (mm).
        trunk_radius: Radius of the trunk cylinder (mm).
        rng: Optional RNG for slight variation.
    """
    if rng is not None:
        height *= rng.uniform(0.85, 1.15)
        canopy_radius *= rng.uniform(0.9, 1.1)

    trunk_height = height * 0.3
    canopy_height = height - trunk_height + BOOLEAN_EMBED

    trunk = cylinder(trunk_radius, trunk_height)
    canopy = cone(canopy_radius, 0.0, canopy_height, segments=12)
    canopy = translate(canopy, z=trunk_height - BOOLEAN_EMBED)

    return union_all([trunk, canopy])


def palm_tree(
    height: float = 6.0,
    trunk_radius: float = 0.4,
    canopy_radius: float = 1.5,
    rng: random.Random | None = None,
) -> Manifold:
    """Palm tree: tall thin trunk with a flared canopy top.

    The canopy is a flat wide cone (like a parasol) sitting on top
    of a tall narrow trunk.

    Args:
        height: Total tree height (mm).
        trunk_radius: Radius of the trunk (mm).
        canopy_radius: Radius of the canopy spread (mm).
        rng: Optional RNG for slight variation.
    """
    if rng is not None:
        height *= rng.uniform(0.9, 1.1)
        canopy_radius *= rng.uniform(0.9, 1.1)

    trunk_height = height * 0.75
    canopy_height = height - trunk_height + BOOLEAN_EMBED

    # Slight taper on trunk (thinner at top)
    trunk = cone(trunk_radius, trunk_radius * 0.7, trunk_height, segments=8)

    # Canopy: inverted cone (wider at bottom, narrow at top) for palm frond look
    canopy = cone(canopy_radius, trunk_radius * 0.5, canopy_height, segments=10)
    canopy = translate(canopy, z=trunk_height - BOOLEAN_EMBED)

    return union_all([trunk, canopy])


# ---------------------------------------------------------------------------
# Hedges
# ---------------------------------------------------------------------------

def hedge_row(
    length: float,
    height: float = 1.5,
    width: float = 1.0,
) -> Manifold:
    """Hedge row: elongated box.

    Aligned along X axis, centered on X/Y, base at Z=0.

    Args:
        length: Length along X (mm).
        height: Height (mm). Default 1.5mm.
        width: Width along Y (mm). Default 1.0mm.
    """
    return box(length, width, height)


# ---------------------------------------------------------------------------
# Swimming pools
# ---------------------------------------------------------------------------

def swimming_pool(
    width: float = 20.0,
    depth: float = 12.0,
    pool_depth: float = 0.5,
    rim_width: float = 0.8,
    rim_height: float = 0.2,
    shape: str = "rectangular",
    rng: random.Random | None = None,
) -> tuple[Manifold, Manifold]:
    """Swimming pool: returns (rim_solid, recess_cutout).

    The rim is unioned onto the base plate surface.
    The recess is subtracted from the base plate to create the pool depression.

    Both are centered on X/Y with base at Z=0.

    Args:
        width: Pool width along X (mm).
        depth: Pool depth along Y (mm).
        pool_depth: How deep the pool recess is (mm).
        rim_width: Width of the raised rim around the pool (mm).
        rim_height: Height of the rim above Z=0 (mm).
        shape: Pool shape: "rectangular", "kidney", or "l_shaped".
        rng: Optional RNG (unused currently, for future shape variation).

    Returns:
        Tuple of (rim_manifold, recess_cutout_manifold).
    """
    if shape == "rectangular":
        return _rectangular_pool(width, depth, pool_depth, rim_width, rim_height)
    elif shape == "kidney":
        return _kidney_pool(width, depth, pool_depth, rim_width, rim_height)
    elif shape == "l_shaped":
        return _l_shaped_pool(width, depth, pool_depth, rim_width, rim_height)
    else:
        raise GeometryError(f"Unknown pool shape: {shape}")


def _rectangular_pool(
    width: float,
    depth: float,
    pool_depth: float,
    rim_width: float,
    rim_height: float,
) -> tuple[Manifold, Manifold]:
    """Rectangular pool with raised rim."""
    # Recess: a box cut into the base plate
    recess = box(width, depth, pool_depth + BOOLEAN_OVERSHOOT)
    recess = translate(recess, z=-pool_depth)

    # Rim: outer box minus inner box
    outer_w = width + 2 * rim_width
    outer_d = depth + 2 * rim_width
    rim_outer = box(outer_w, outer_d, rim_height)
    rim_cutout = box(width, depth, rim_height + 2 * BOOLEAN_OVERSHOOT)
    rim_cutout = translate(rim_cutout, z=-BOOLEAN_OVERSHOOT)
    rim = rim_outer - rim_cutout

    return rim, recess


def _kidney_pool(
    width: float,
    depth: float,
    pool_depth: float,
    rim_width: float,
    rim_height: float,
) -> tuple[Manifold, Manifold]:
    """Kidney-shaped pool: two overlapping circles of different sizes."""
    r_large = min(width, depth) * 0.4
    r_small = r_large * 0.7
    offset = r_large * 0.5

    # Pool shape: union of two cylinders
    c1 = cylinder(r_large, pool_depth + BOOLEAN_OVERSHOOT, segments=16)
    c1 = translate(c1, x=-offset * 0.3, z=-pool_depth)
    c2 = cylinder(r_small, pool_depth + BOOLEAN_OVERSHOOT, segments=16)
    c2 = translate(c2, x=offset * 0.7, y=offset * 0.3, z=-pool_depth)
    recess = union_all([c1, c2])

    # Rim: scaled-up pool shape minus pool shape
    c1_rim = cylinder(r_large + rim_width, rim_height, segments=16)
    c1_rim = translate(c1_rim, x=-offset * 0.3)
    c2_rim = cylinder(r_small + rim_width, rim_height, segments=16)
    c2_rim = translate(c2_rim, x=offset * 0.7, y=offset * 0.3)
    rim_outer = union_all([c1_rim, c2_rim])

    c1_cut = cylinder(r_large, rim_height + 2 * BOOLEAN_OVERSHOOT, segments=16)
    c1_cut = translate(c1_cut, x=-offset * 0.3, z=-BOOLEAN_OVERSHOOT)
    c2_cut = cylinder(r_small, rim_height + 2 * BOOLEAN_OVERSHOOT, segments=16)
    c2_cut = translate(c2_cut, x=offset * 0.7, y=offset * 0.3, z=-BOOLEAN_OVERSHOOT)
    rim_cut = union_all([c1_cut, c2_cut])

    rim = rim_outer - rim_cut

    return rim, recess


def _l_shaped_pool(
    width: float,
    depth: float,
    pool_depth: float,
    rim_width: float,
    rim_height: float,
) -> tuple[Manifold, Manifold]:
    """L-shaped pool: two overlapping rectangles."""
    # Main rectangle: full width, half depth
    w1, d1 = width, depth * 0.5
    # Side rectangle: half width, full depth, offset to one side
    w2, d2 = width * 0.5, depth

    r1 = box(w1, d1, pool_depth + BOOLEAN_OVERSHOOT)
    r1 = translate(r1, y=-depth * 0.25, z=-pool_depth)
    r2 = box(w2, d2, pool_depth + BOOLEAN_OVERSHOOT)
    r2 = translate(r2, x=-width * 0.25, z=-pool_depth)
    recess = union_all([r1, r2])

    # Rim
    r1_outer = box(w1 + 2 * rim_width, d1 + 2 * rim_width, rim_height)
    r1_outer = translate(r1_outer, y=-depth * 0.25)
    r2_outer = box(w2 + 2 * rim_width, d2 + 2 * rim_width, rim_height)
    r2_outer = translate(r2_outer, x=-width * 0.25)
    rim_outer = union_all([r1_outer, r2_outer])

    r1_cut = box(w1, d1, rim_height + 2 * BOOLEAN_OVERSHOOT)
    r1_cut = translate(r1_cut, y=-depth * 0.25, z=-BOOLEAN_OVERSHOOT)
    r2_cut = box(w2, d2, rim_height + 2 * BOOLEAN_OVERSHOOT)
    r2_cut = translate(r2_cut, x=-width * 0.25, z=-BOOLEAN_OVERSHOOT)
    rim_cut = union_all([r1_cut, r2_cut])

    rim = rim_outer - rim_cut

    return rim, recess


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def garden_path(
    points: list[tuple[float, float]],
    width: float = 2.0,
    height: float = 0.3,
) -> Manifold:
    """Garden path: slightly raised strip connecting waypoints.

    Built as a union of box segments, one for each pair of consecutive
    points. Each segment is rotated and positioned to connect the points.

    Args:
        points: List of (x, y) waypoints along the path.
        width: Path width (mm).
        height: Path height above Z=0 (mm).

    Returns:
        Union of all path segments.
    """
    if len(points) < 2:
        raise GeometryError("Path needs at least 2 points")

    segments: list[Manifold] = []
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 0.01:
            continue
        angle = math.degrees(math.atan2(dy, dx))

        seg = box(length + BOOLEAN_EMBED, width, height)
        seg = rotate_z(seg, angle)
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        seg = translate(seg, x=mid_x, y=mid_y)
        segments.append(seg)

    if not segments:
        raise GeometryError("Path produced no valid segments")
    return union_all(segments)


# ---------------------------------------------------------------------------
# Terraces
# ---------------------------------------------------------------------------

def terrace(
    width: float,
    depth: float,
    height: float = 0.5,
) -> Manifold:
    """Flat raised platform, e.g., a patio or entrance plaza.

    Args:
        width: Width along X (mm).
        depth: Depth along Y (mm).
        height: Height above Z=0 (mm).
    """
    return box(width, depth, height)

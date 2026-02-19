"""Geometry primitives with dimension guards.

All primitives validate inputs and raise GeometryError on invalid dimensions.
"""

import math

import numpy as np
from manifold3d import CrossSection, Manifold

from hotel_generator.errors import GeometryError

# Boolean operation constants
BOOLEAN_OVERSHOOT = 0.1  # Extend subtractions past the target surface (mm)
BOOLEAN_EMBED = 0.1  # Embed additive features into the target surface (mm)
COPLANAR_OFFSET = 0.01  # Minimum offset to avoid coplanar faces (mm)


def _check_positive(value: float, name: str) -> None:
    """Raise GeometryError if value is not positive."""
    if value <= 0:
        raise GeometryError(f"{name} must be positive, got {value}")


def box(width: float, depth: float, height: float) -> Manifold:
    """Create a box centered on X/Y with base at Z=0.

    Args:
        width: Size along X axis (mm).
        depth: Size along Y axis (mm).
        height: Size along Z axis (mm).
    """
    _check_positive(width, "width")
    _check_positive(depth, "depth")
    _check_positive(height, "height")
    return Manifold.cube([width, depth, height]).translate(
        [-width / 2, -depth / 2, 0]
    )


def cylinder(
    radius: float, height: float, segments: int | None = None
) -> Manifold:
    """Create a cylinder centered on X/Y with base at Z=0.

    Args:
        radius: Cylinder radius (mm).
        height: Cylinder height (mm).
        segments: Number of segments. None uses the global default.
    """
    _check_positive(radius, "radius")
    _check_positive(height, "height")
    if segments is not None:
        return Manifold.cylinder(height, radius, circular_segments=segments)
    return Manifold.cylinder(height, radius)


def cone(
    r_bottom: float,
    r_top: float,
    height: float,
    segments: int | None = None,
) -> Manifold:
    """Create a tapered cylinder (cone/frustum) centered on X/Y with base at Z=0.

    Args:
        r_bottom: Bottom radius (mm). Must be positive.
        r_top: Top radius (mm). Can be 0 for a true cone.
        height: Height (mm).
        segments: Number of segments. None uses the global default.
    """
    _check_positive(r_bottom, "r_bottom")
    if r_top < 0:
        raise GeometryError(f"r_top must be non-negative, got {r_top}")
    _check_positive(height, "height")
    if segments is not None:
        return Manifold.cylinder(
            height, r_bottom, r_top, circular_segments=segments
        )
    return Manifold.cylinder(height, r_bottom, r_top)


def extrude_polygon(points: list[tuple[float, float]], height: float) -> Manifold:
    """Extrude a 2D polygon along Z.

    Args:
        points: List of (x, y) polygon vertices in counter-clockwise order.
        height: Extrusion height (mm).
    """
    _check_positive(height, "height")
    if len(points) < 3:
        raise GeometryError(f"Polygon needs at least 3 points, got {len(points)}")
    cs = CrossSection([points])
    result = Manifold.extrude(cs, height)
    if result.is_empty():
        raise GeometryError("Extrude produced an empty manifold (degenerate polygon?)")
    return result


def revolve_profile(
    points: list[tuple[float, float]],
    segments: int = 32,
    degrees: float = 360.0,
) -> Manifold:
    """Revolve a 2D profile around the Y axis.

    The profile is defined in the XZ plane (X = radius, Z = height).
    Points should form a closed polygon with X >= 0.

    Args:
        points: List of (x, z) profile vertices.
        segments: Number of rotation segments.
        degrees: Rotation angle in degrees (360 = full revolution).
    """
    if len(points) < 3:
        raise GeometryError(f"Profile needs at least 3 points, got {len(points)}")
    _check_positive(degrees, "degrees")
    cs = CrossSection([points])
    result = Manifold.revolve(cs, circular_segments=segments, revolve_degrees=degrees)
    if result.is_empty():
        raise GeometryError("Revolve produced an empty manifold")
    return result


def debug_manifold(m: Manifold, label: str = "manifold") -> None:
    """Print debug info about a manifold for troubleshooting."""
    if m.is_empty():
        print(f"[DEBUG] {label}: EMPTY")
        return
    min_x, min_y, min_z, max_x, max_y, max_z = m.bounding_box()
    print(
        f"[DEBUG] {label}: volume={m.volume():.4f}, "
        f"bbox=({min_x:.2f},{min_y:.2f},{min_z:.2f})-"
        f"({max_x:.2f},{max_y:.2f},{max_z:.2f})"
    )

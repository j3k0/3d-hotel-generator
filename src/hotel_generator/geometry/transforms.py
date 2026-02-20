"""Transform utilities with safe_scale wrapper.

CRITICAL: Never use Manifold.scale(float) — it crashes Python bindings
in manifold3d 3.3.2. Always use safe_scale() which passes a 3-vector.
"""

import math

import numpy as np
from manifold3d import Manifold


def translate(solid: Manifold, x: float = 0, y: float = 0, z: float = 0) -> Manifold:
    """Translate a manifold by (x, y, z)."""
    return solid.translate([x, y, z])


def rotate_x(solid: Manifold, degrees: float) -> Manifold:
    """Rotate a manifold around the X axis."""
    return solid.rotate([degrees, 0, 0])


def rotate_y(solid: Manifold, degrees: float) -> Manifold:
    """Rotate a manifold around the Y axis."""
    return solid.rotate([0, degrees, 0])


def rotate_z(solid: Manifold, degrees: float) -> Manifold:
    """Rotate a manifold around the Z axis."""
    return solid.rotate([0, 0, degrees])


def mirror_x(solid: Manifold) -> Manifold:
    """Mirror a manifold across the YZ plane (flip X)."""
    return solid.mirror([1, 0, 0])


def mirror_y(solid: Manifold) -> Manifold:
    """Mirror a manifold across the XZ plane (flip Y)."""
    return solid.mirror([0, 1, 0])


def safe_scale(
    solid: Manifold, sx: float = 1.0, sy: float = 1.0, sz: float = 1.0
) -> Manifold:
    """Scale a manifold using the 3-vector form.

    NEVER use Manifold.scale(float) — it crashes in manifold3d 3.3.2.
    This function always passes [sx, sy, sz].
    """
    return solid.scale([sx, sy, sz])


def bend_around_z(
    solid: Manifold,
    bend_angle_degrees: float,
    max_edge_length: float = 1.0,
) -> Manifold:
    """Bend a manifold around the vertical (Z) axis.

    Maps the X dimension to an angular arc and Y to radial distance,
    creating a curved building. The front face (-Y) ends up on the
    concave (inner) side of the arc.

    The bend radius is auto-calculated from the solid's X extent and
    the requested angle so arc length equals the original width.

    Args:
        solid: The manifold to bend. Should be centered on X.
        bend_angle_degrees: Total angular span in degrees. Positive =
            concave side faces -Y (forward). Typical values: 60-180.
        max_edge_length: Maximum triangle edge length after refinement.
            Smaller = smoother curve but more triangles. Default 1.0mm.

    Returns:
        Bent manifold, re-centered so the midpoint of the arc is at
        the origin in X/Y.
    """
    if abs(bend_angle_degrees) < 1e-3:
        return solid  # no-op for zero bend

    bend_angle = math.radians(bend_angle_degrees)

    # Get bounding box to determine X extent
    min_x, min_y, min_z, max_x, max_y, max_z = solid.bounding_box()
    width = max_x - min_x
    center_x = (min_x + max_x) / 2.0

    if width < 1e-6:
        return solid

    # bend_radius = arc_length / angle, where arc_length = width
    bend_radius = width / abs(bend_angle)

    # Refine mesh so the curve is smooth
    refined = solid.refine_to_length(max_edge_length)

    # Vectorized warp: map X to angle, Y to radial offset
    def _warp_batch(verts: np.ndarray) -> np.ndarray:
        x = verts[:, 0]
        y = verts[:, 1]
        z = verts[:, 2]

        # Normalized position along width: -0.5 to 0.5
        t = (x - center_x) / width
        theta = t * bend_angle

        r = bend_radius + y
        new_x = r * np.sin(theta)
        new_y = r * np.cos(theta) - bend_radius
        return np.column_stack([new_x, new_y, z])

    return refined.warp_batch(_warp_batch)

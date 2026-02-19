"""Transform utilities with safe_scale wrapper.

CRITICAL: Never use Manifold.scale(float) — it crashes Python bindings
in manifold3d 3.3.2. Always use safe_scale() which passes a 3-vector.
"""

import math

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

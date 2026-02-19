"""Door cutout and canopy components."""

from manifold3d import Manifold

from hotel_generator.geometry.primitives import box, extrude_polygon, BOOLEAN_OVERSHOOT
from hotel_generator.geometry.booleans import union_all
from hotel_generator.geometry.transforms import translate


def door_cutout(
    width: float,
    height: float,
    wall_thickness: float,
) -> Manifold:
    """Create a door cutout that overshoots the wall.

    Centered on X, at Y=0, base at Z=0.
    """
    return box(
        width,
        wall_thickness + 2 * BOOLEAN_OVERSHOOT,
        height,
    )


def door_canopy(
    width: float,
    depth: float,
    thickness: float = 0.3,
    support_angle: float = 45.0,
) -> Manifold:
    """Create a door canopy with 45-degree underside support.

    Positioned with back face at Y=0, extending forward.
    Base at Z=0.
    """
    # Canopy slab
    canopy = box(width, depth, thickness)

    # 45-degree support wedge underneath
    import math
    wedge_height = depth * math.tan(math.radians(support_angle))
    if wedge_height > thickness:
        wedge_height = thickness

    wedge = extrude_polygon(
        [(0, 0), (depth, 0), (0, wedge_height)],
        width,
    )
    wedge = translate(wedge, x=-width / 2)
    # Position wedge under canopy
    wedge = translate(wedge, z=-wedge_height)

    result = union_all([canopy, wedge])
    return result

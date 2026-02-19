"""Window cutout and frame components."""

from manifold3d import Manifold

from hotel_generator.geometry.primitives import (
    box,
    cylinder,
    BOOLEAN_OVERSHOOT,
    BOOLEAN_EMBED,
)
from hotel_generator.geometry.booleans import union_all
from hotel_generator.geometry.transforms import translate


def window_cutout(
    width: float,
    height: float,
    wall_thickness: float,
) -> Manifold:
    """Create a rectangular window cutout that overshoots the wall.

    Centered on X/Y, base at Z=0. The cutout extends BOOLEAN_OVERSHOOT
    past the wall on both sides along Y.

    Args:
        width: Window width (mm).
        height: Window height (mm).
        wall_thickness: Full wall thickness for overshoot (mm).
    """
    return box(
        width,
        wall_thickness + 2 * BOOLEAN_OVERSHOOT,
        height,
    )


def arched_window_cutout(
    width: float,
    height: float,
    wall_thickness: float,
    segments: int = 16,
) -> Manifold:
    """Create an arched window cutout (resin-only).

    Rectangle with a semicircular top. Centered on X/Y, base at Z=0.
    """
    depth = wall_thickness + 2 * BOOLEAN_OVERSHOOT
    radius = width / 2

    # Rectangular part (up to the start of the arch)
    rect_height = height - radius
    if rect_height <= 0:
        rect_height = height * 0.5
        radius = height - rect_height

    rect = box(width, depth, rect_height)

    # Semicircular arch on top
    arch = cylinder(radius, depth, segments=segments)
    # Cylinder is along Z, we need it along Y
    arch = arch.rotate([90, 0, 0])
    arch = translate(arch, y=depth / 2, z=rect_height)

    return union_all([rect, arch])


def window_frame(
    width: float,
    height: float,
    frame_width: float = 0.15,
    frame_depth: float = 0.1,
) -> Manifold:
    """Create a window frame that sits on the wall surface.

    Frame is a rectangular border around the window opening.
    Centered on X, front face at Y=0, base at Z=0.
    """
    outer = box(
        width + 2 * frame_width,
        frame_depth,
        height + 2 * frame_width,
    )
    inner = box(width, frame_depth + 0.1, height)
    inner = translate(inner, z=frame_width)

    frame = outer - inner
    frame = translate(frame, z=-frame_width)
    return frame

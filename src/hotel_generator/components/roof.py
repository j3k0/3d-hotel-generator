"""Roof generators: flat, gabled, hipped, mansard, barrel."""

from manifold3d import Manifold

from hotel_generator.geometry.primitives import (
    box,
    extrude_polygon,
    cylinder,
    BOOLEAN_EMBED,
)
from hotel_generator.geometry.booleans import union_all
from hotel_generator.geometry.transforms import translate, rotate_z, rotate_x


def flat_roof(
    width: float,
    depth: float,
    parapet_height: float = 0.5,
    slab_thickness: float = 0.3,
) -> Manifold:
    """Flat roof with optional parapet. Base at Z=0.

    Args:
        width: Roof width (mm).
        depth: Roof depth (mm).
        parapet_height: Height of parapet walls above roof (mm). 0 = no parapet.
        slab_thickness: Roof slab thickness (mm).
    """
    slab = box(width, depth, slab_thickness)

    if parapet_height <= 0:
        return slab

    # Parapet walls around the edge
    pw = 0.3  # parapet wall thickness
    parts = [slab]

    # Front parapet
    front = box(width, pw, parapet_height + slab_thickness)
    front = translate(front, y=-depth / 2 + pw / 2)
    parts.append(front)

    # Back parapet
    back = box(width, pw, parapet_height + slab_thickness)
    back = translate(back, y=depth / 2 - pw / 2)
    parts.append(back)

    # Left parapet
    left = box(pw, depth, parapet_height + slab_thickness)
    left = translate(left, x=-width / 2 + pw / 2)
    parts.append(left)

    # Right parapet
    right = box(pw, depth, parapet_height + slab_thickness)
    right = translate(right, x=width / 2 - pw / 2)
    parts.append(right)

    return union_all(parts)


def gabled_roof(
    width: float,
    depth: float,
    peak_height: float,
) -> Manifold:
    """Gabled (triangular) roof via extruded triangle. Base at Z=0.

    Ridge runs along Y axis. Gable faces are on the X ends.
    """
    # Triangle cross-section in XY plane, extruded along Z
    half_w = width / 2
    profile = [
        (-half_w, 0),
        (half_w, 0),
        (0, peak_height),
    ]
    # Extrude along Z (becomes depth), then rotate so depth runs along Y
    prism = extrude_polygon(profile, depth)
    # After extrude: X = width, Y = [0, peak_height], Z = [0, depth]
    # rotate_x(90): Y -> -Z, Z -> Y  (but Z was [0,d] so new Y = [-d, 0])
    # Then translate(y=d/2) centers on Y, Z = [0, peak_height]
    prism = rotate_x(prism, 90)
    prism = translate(prism, y=depth / 2)
    return prism


def hipped_roof(
    width: float,
    depth: float,
    peak_height: float,
) -> Manifold:
    """Hipped roof (all four sides slope inward). Base at Z=0.

    Created by intersecting two gabled roofs perpendicular to each other.
    The gables are made oversized so their intersection covers the full footprint.
    """
    # Gable with ridge along Y (slopes on X sides), extended along Y
    gable_y = gabled_roof(width, depth + width * 2, peak_height)

    # Gable with ridge along X (slopes on Y sides), extended along X
    gable_x = gabled_roof(depth, width + depth * 2, peak_height)
    gable_x = rotate_z(gable_x, 90)

    # Intersection produces the hip shape
    result = gable_y ^ gable_x
    if result.is_empty():
        # Fallback: just use a simple gabled roof
        return gabled_roof(width, depth, peak_height)
    return result


def mansard_roof(
    width: float,
    depth: float,
    lower_height: float,
    upper_height: float,
    inset: float = 0.8,
) -> Manifold:
    """Mansard roof (steep lower slope + shallow upper section). Base at Z=0.

    Args:
        width: Base width (mm).
        depth: Base depth (mm).
        lower_height: Height of steep lower section (mm).
        upper_height: Height of upper flat/shallow section (mm).
        inset: How far the upper section is inset from the edges (mm).
    """
    # Lower section: truncated pyramid (box tapering inward)
    half_w = width / 2
    half_d = depth / 2
    inner_hw = half_w - inset
    inner_hd = half_d - inset

    # Create as extruded polygon (side profile, then intersect)
    # Simpler: use two boxes with intersection
    lower = box(width, depth, lower_height)

    # Upper section
    upper = box(width - 2 * inset, depth - 2 * inset, upper_height)
    upper = translate(upper, z=lower_height)

    # For a proper mansard, we want the lower part to slope.
    # Use hipped roof shape for the lower part, then add flat top
    lower_hip = hipped_roof(width, depth, lower_height + upper_height + 1)
    # Clip at lower_height
    clip = box(width + 1, depth + 1, lower_height)
    lower_clipped = lower_hip ^ clip

    return union_all([lower_clipped, upper])


def barrel_roof(
    width: float,
    depth: float,
    height: float,
    segments: int = 16,
) -> Manifold:
    """Barrel (half-cylinder) roof. Base at Z=0. Curve runs along Y.

    Args:
        width: Roof width (mm) = diameter of the barrel.
        depth: Roof depth (mm) = length of the barrel.
        height: Peak height of the barrel above base (mm).
        segments: Number of circular segments.
    """
    radius = width / 2
    # Scale height: if height != radius, we scale Z
    cyl = cylinder(radius, depth, segments=segments)
    # Cylinder is along Z by default. Rotate to run along Y.
    cyl = rotate_x(cyl, -90)
    cyl = translate(cyl, y=depth / 2)

    # Cut to only keep top half
    cutter = box(width + 1, depth + 1, radius + 1)
    cutter = translate(cutter, z=-(radius + 1))
    cyl = cyl - cutter

    # Scale height if needed
    if abs(height - radius) > 0.01:
        from hotel_generator.geometry.transforms import safe_scale
        scale_z = height / radius if radius > 0 else 1.0
        cyl = safe_scale(cyl, 1.0, 1.0, scale_z)

    return cyl

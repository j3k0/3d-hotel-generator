"""Base/pedestal slab with chamfer for bed adhesion and stability."""

from manifold3d import Manifold

from hotel_generator.geometry.primitives import box, extrude_polygon, BOOLEAN_EMBED
from hotel_generator.geometry.booleans import difference_all
from hotel_generator.geometry.transforms import translate, rotate_z


def base_slab(
    width: float,
    depth: float,
    thickness: float = 1.2,
    chamfer: float = 0.3,
) -> Manifold:
    """Create a base slab with 45-degree chamfer on the bottom edge.

    The slab is centered on X/Y with its top face at Z=0 and bottom
    at Z=-thickness, so that building walls sit directly on top.

    Args:
        width: Total width including overhang (mm).
        depth: Total depth including overhang (mm).
        thickness: Slab thickness (mm). 1.2 FDM / 1.0 resin.
        chamfer: 45-degree chamfer size on bottom edge (mm). 0.3 FDM / 0.2 resin.
    """
    slab = box(width, depth, thickness)
    slab = translate(slab, z=-thickness)

    if chamfer <= 0:
        return slab

    # Subtract 45-degree triangular wedges from the four bottom edges
    cuts = []

    # Front edge (along X, at -depth/2, z=-thickness)
    tri = extrude_polygon(
        [(0, 0), (chamfer, 0), (0, chamfer)],
        width + 0.2,
    )
    tri_front = translate(tri, x=-width / 2 - 0.1, y=-depth / 2, z=-thickness)
    cuts.append(tri_front)

    # Back edge
    tri_back = rotate_z(
        extrude_polygon([(0, 0), (chamfer, 0), (0, chamfer)], width + 0.2),
        180,
    )
    tri_back = translate(tri_back, x=width / 2 + 0.1, y=depth / 2, z=-thickness)
    cuts.append(tri_back)

    # Left edge (along Y)
    tri_left = rotate_z(
        extrude_polygon([(0, 0), (chamfer, 0), (0, chamfer)], depth + 0.2),
        90,
    )
    tri_left = translate(tri_left, x=-width / 2, y=-depth / 2 - 0.1, z=-thickness)
    cuts.append(tri_left)

    # Right edge
    tri_right = rotate_z(
        extrude_polygon([(0, 0), (chamfer, 0), (0, chamfer)], depth + 0.2),
        -90,
    )
    tri_right = translate(tri_right, x=width / 2, y=depth / 2 + 0.1, z=-thickness)
    cuts.append(tri_right)

    return difference_all(slab, cuts)

"""Balcony component with slab and railing."""

from manifold3d import Manifold

from hotel_generator.geometry.primitives import box, extrude_polygon, BOOLEAN_EMBED
from hotel_generator.geometry.booleans import union_all
from hotel_generator.geometry.transforms import translate


def balcony(
    width: float,
    depth: float,
    slab_thickness: float = 0.2,
    railing_height: float = 0.5,
    railing_thickness: float = 0.2,
    use_solid_railing: bool = True,
    add_support: bool = True,
) -> Manifold:
    """Create a balcony with slab, railing, and optional support wedge.

    Centered on X. Slab extends from Y=0 (wall face) to Y=depth.
    Base at Z=0.

    Args:
        width: Balcony width (mm).
        depth: Balcony depth (mm).
        slab_thickness: Thickness of the floor slab (mm).
        railing_height: Height of the railing above slab (mm).
        railing_thickness: Thickness of railing walls (mm).
        use_solid_railing: True=solid wall (FDM), False=open railing (resin).
        add_support: Add 45-degree support wedge underneath for FDM.
    """
    parts = []

    # Floor slab
    slab = box(width, depth, slab_thickness)
    slab = translate(slab, y=depth / 2)
    parts.append(slab)

    # Railing
    if use_solid_railing:
        # Three-sided solid railing (open at wall side)
        # Front
        front_rail = box(width, railing_thickness, railing_height)
        front_rail = translate(
            front_rail,
            y=depth - railing_thickness / 2,
            z=slab_thickness,
        )
        parts.append(front_rail)

        # Left side
        left_rail = box(railing_thickness, depth, railing_height)
        left_rail = translate(
            left_rail,
            x=-width / 2 + railing_thickness / 2,
            y=depth / 2,
            z=slab_thickness,
        )
        parts.append(left_rail)

        # Right side
        right_rail = box(railing_thickness, depth, railing_height)
        right_rail = translate(
            right_rail,
            x=width / 2 - railing_thickness / 2,
            y=depth / 2,
            z=slab_thickness,
        )
        parts.append(right_rail)

    # Support wedge underneath (45-degree for FDM)
    if add_support:
        wedge = extrude_polygon(
            [(0, 0), (depth, 0), (0, depth)],
            width,
        )
        wedge = translate(wedge, x=-width / 2, z=-depth)
        parts.append(wedge)

    return union_all(parts)

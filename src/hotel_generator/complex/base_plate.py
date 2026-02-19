"""Shared base plate for hotel complexes."""

from __future__ import annotations

from manifold3d import Manifold

from hotel_generator.config import BuildingPlacement
from hotel_generator.components.base import base_slab
from hotel_generator.geometry.primitives import box, BOOLEAN_EMBED
from hotel_generator.geometry.transforms import translate
from hotel_generator.geometry.booleans import union_all


def complex_base_plate(
    lot_width: float,
    lot_depth: float,
    thickness: float,
    chamfer: float,
    placements: list[BuildingPlacement] | None = None,
    recess_depth: float = 0.3,
) -> Manifold:
    """Generate a shared base plate for a hotel complex.

    Args:
        lot_width: Total lot width (mm).
        lot_depth: Total lot depth (mm).
        thickness: Slab thickness (mm).
        chamfer: Edge chamfer size (mm).
        placements: Optional building placements for alignment recesses.
        recess_depth: Depth of alignment recesses (mm).
    """
    plate = base_slab(lot_width, lot_depth, thickness, chamfer)

    # Add shallow recesses at building positions for alignment
    if placements and recess_depth > 0:
        recesses = []
        for p in placements:
            rot = p.rotation % 360
            if rot in (90, 270):
                rw, rd = p.depth, p.width
            else:
                rw, rd = p.width, p.depth
            recess = box(rw + 0.2, rd + 0.2, recess_depth + BOOLEAN_EMBED)
            recess = translate(recess, x=p.x, y=p.y, z=-recess_depth)
            recesses.append(recess)

        from hotel_generator.geometry.booleans import difference_all
        plate = difference_all(plate, recesses)

    return plate

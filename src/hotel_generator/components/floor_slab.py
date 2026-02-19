"""Floor slab (horizontal divider between floors)."""

from manifold3d import Manifold

from hotel_generator.geometry.primitives import box
from hotel_generator.geometry.transforms import translate


def floor_slab(
    width: float,
    depth: float,
    thickness: float = 0.15,
    overhang: float = 0.0,
) -> Manifold:
    """Create a horizontal floor slab. Centered on X/Y, base at Z=0.

    Args:
        width: Slab width (mm).
        depth: Slab depth (mm).
        thickness: Slab thickness (mm).
        overhang: How far slab extends past the walls on each side (mm).
    """
    return box(width + 2 * overhang, depth + 2 * overhang, thickness)

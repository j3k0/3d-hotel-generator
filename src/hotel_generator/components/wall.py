"""Wall component — solid box with parametric dimensions."""

from manifold3d import Manifold

from hotel_generator.geometry.primitives import box
from hotel_generator.geometry.transforms import translate


def wall(
    width: float,
    height: float,
    thickness: float = 0.8,
) -> Manifold:
    """Create a wall panel centered on X, with front face at Y=0.

    Base at Z=0, extends upward by height.

    Args:
        width: Wall width along X (mm).
        height: Wall height along Z (mm).
        thickness: Wall thickness along Y (mm).
    """
    return box(width, thickness, height).translate([0, -thickness / 2, 0])

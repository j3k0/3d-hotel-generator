"""Column and pilaster components."""

from manifold3d import Manifold

from hotel_generator.geometry.primitives import box, cylinder


def round_column(
    radius: float,
    height: float,
    segments: int | None = None,
) -> Manifold:
    """Create a round column centered on X/Y, base at Z=0."""
    return cylinder(radius, height, segments=segments)


def square_column(
    width: float,
    height: float,
) -> Manifold:
    """Create a square column centered on X/Y, base at Z=0.

    Square columns print more reliably on FDM at small sizes.
    """
    return box(width, width, height)


def pilaster(
    width: float,
    depth: float,
    height: float,
) -> Manifold:
    """Create a pilaster (flat column that projects from a wall).

    Centered on X, front face at Y=0, base at Z=0.
    """
    return box(width, depth, height)

"""Floor plan massing shapes for different architectural styles."""

from manifold3d import Manifold

from hotel_generator.geometry.primitives import box
from hotel_generator.geometry.booleans import union_all
from hotel_generator.geometry.transforms import translate


def rect_mass(width: float, depth: float, height: float) -> Manifold:
    """Simple rectangular massing. Base at Z=0."""
    return box(width, depth, height)


def l_shape_mass(
    width: float,
    depth: float,
    height: float,
    wing_width: float | None = None,
    wing_depth: float | None = None,
) -> Manifold:
    """L-shaped plan (main block + perpendicular wing). Base at Z=0.

    The main block is centered; the wing extends from one corner.
    """
    ww = wing_width or width * 0.5
    wd = wing_depth or depth * 0.6

    main = box(width, depth, height)
    wing = box(ww, wd, height)
    wing = translate(wing, x=(width - ww) / 2, y=(depth + wd) / 2 - wd * 0.3)
    return union_all([main, wing])


def u_shape_mass(
    width: float,
    depth: float,
    height: float,
    courtyard_width: float | None = None,
    courtyard_depth: float | None = None,
) -> Manifold:
    """U-shaped plan (three sides around a courtyard). Base at Z=0."""
    cw = courtyard_width or width * 0.5
    cd = courtyard_depth or depth * 0.5
    wall_w = (width - cw) / 2

    # Back wall (full width)
    back = box(width, depth - cd, height)
    back = translate(back, y=(depth - (depth - cd)) / 2)

    # Left wing
    left = box(wall_w, depth, height)
    left = translate(left, x=-(width - wall_w) / 2)

    # Right wing
    right = box(wall_w, depth, height)
    right = translate(right, x=(width - wall_w) / 2)

    return union_all([back, left, right])


def t_shape_mass(
    width: float,
    depth: float,
    height: float,
    top_width: float | None = None,
    top_depth: float | None = None,
) -> Manifold:
    """T-shaped plan (main block with a wider top). Base at Z=0."""
    tw = top_width or width * 1.3
    td = top_depth or depth * 0.4

    main = box(width, depth, height)
    top = box(tw, td, height)
    top = translate(top, y=(depth + td) / 2 - td * 0.2)
    return union_all([main, top])


def podium_tower_mass(
    podium_width: float,
    podium_depth: float,
    podium_height: float,
    tower_width: float,
    tower_depth: float,
    tower_height: float,
) -> Manifold:
    """Podium + tower massing for skyscrapers. Base at Z=0."""
    podium = box(podium_width, podium_depth, podium_height)
    tower = box(tower_width, tower_depth, tower_height)
    tower = translate(tower, z=podium_height)
    return union_all([podium, tower])


def stepped_mass(
    base_width: float,
    base_depth: float,
    num_tiers: int,
    tier_height: float,
    setback: float = 0.5,
) -> Manifold:
    """Stepped/ziggurat massing for Art Deco. Base at Z=0.

    Each tier is smaller than the one below by `setback` on each side.
    """
    tiers = []
    for i in range(num_tiers):
        w = base_width - 2 * setback * i
        d = base_depth - 2 * setback * i
        if w <= 0 or d <= 0:
            break
        tier = box(w, d, tier_height)
        tier = translate(tier, z=i * tier_height)
        tiers.append(tier)
    return union_all(tiers)

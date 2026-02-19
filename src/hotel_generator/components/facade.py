"""Facade composition — place windows and doors on walls at grid positions."""

from manifold3d import Manifold

from hotel_generator.geometry.transforms import translate
from hotel_generator.components.window import window_cutout


def window_grid_cutouts(
    wall_width: float,
    wall_height: float,
    wall_thickness: float,
    num_floors: int,
    floor_height: float,
    windows_per_floor: int,
    window_width: float,
    window_height: float,
    first_floor_offset: float = 0.0,
    ground_floor_skip: bool = True,
) -> list[Manifold]:
    """Generate a grid of window cutouts positioned on a wall.

    Returns a list of Manifold cutouts ready to be subtracted from
    the building shell.

    Args:
        wall_width: Width of the wall (mm).
        wall_height: Total wall height (mm).
        wall_thickness: Thickness for cutout overshoot (mm).
        num_floors: Number of floors.
        floor_height: Height per floor (mm).
        windows_per_floor: Number of windows per floor.
        window_width: Width of each window (mm).
        window_height: Height of each window (mm).
        first_floor_offset: Z offset for ground floor (mm).
        ground_floor_skip: Skip windows on ground floor (for doors).
    """
    cutouts = []

    start_floor = 1 if ground_floor_skip else 0

    for floor_idx in range(start_floor, num_floors):
        # Window centers evenly spaced across wall width
        spacing = wall_width / (windows_per_floor + 1)

        for win_idx in range(windows_per_floor):
            x_pos = -wall_width / 2 + spacing * (win_idx + 1)
            z_pos = floor_idx * floor_height + first_floor_offset + (
                floor_height - window_height
            ) / 2

            cut = window_cutout(window_width, window_height, wall_thickness)
            cut = translate(cut, x=x_pos, z=z_pos)
            cutouts.append(cut)

    return cutouts

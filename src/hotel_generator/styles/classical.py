"""Classical style: columns, pediment, symmetric facade."""

from __future__ import annotations

import random
from typing import Any

from manifold3d import Manifold

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.geometry.primitives import (
    box,
    extrude_polygon,
    BOOLEAN_EMBED,
    BOOLEAN_OVERSHOOT,
)
from hotel_generator.geometry.transforms import translate, rotate_x
from hotel_generator.components.massing import rect_mass
from hotel_generator.components.facade import window_grid_cutouts
from hotel_generator.components.door import door_cutout
from hotel_generator.components.column import square_column, round_column
from hotel_generator.styles.base import HotelStyle, register_style, assemble_building


@register_style
class ClassicalStyle(HotelStyle):
    @property
    def name(self) -> str:
        return "classical"

    @property
    def display_name(self) -> str:
        return "Classical"

    @property
    def description(self) -> str:
        return "Symmetric facade with columns, entablature, and triangular pediment"

    def generate(self, params: BuildingParams, profile: PrinterProfile) -> Manifold:
        rng = random.Random(params.seed)
        w = params.width
        d = params.depth
        num_floors = params.num_floors
        fh = params.floor_height
        wall_t = profile.min_wall_thickness
        total_h = num_floors * fh

        shell = rect_mass(w, d, total_h)

        # Windows
        cutouts = []
        win_w = 0.4
        win_h = 0.5
        wins_per_floor = max(2, int(w / 1.8))

        for y_sign in [-1, 1]:
            cuts = window_grid_cutouts(
                wall_width=w,
                wall_height=total_h,
                wall_thickness=wall_t,
                num_floors=num_floors,
                floor_height=fh,
                windows_per_floor=wins_per_floor,
                window_width=win_w,
                window_height=win_h,
            )
            for c in cuts:
                cutouts.append(translate(c, y=y_sign * d / 2))

        # Grand entrance door
        door_w = max(1.0, w * 0.15)
        door_h = fh * 0.9
        door = door_cutout(door_w, door_h, wall_t)
        cutouts.append(translate(door, y=-d / 2))

        # Additions
        additions = []

        # Entablature (horizontal band at top of columns)
        entablature_h = 0.3
        entablature = box(w + 0.4, d + 0.4, entablature_h)
        entablature = translate(entablature, z=total_h - BOOLEAN_EMBED)
        additions.append(entablature)

        # Triangular pediment on front facade
        pediment_h = fh * 0.8
        half_w = (w + 0.4) / 2
        pediment_profile = [(-half_w, 0), (half_w, 0), (0, pediment_h)]
        pediment_depth = 0.4
        pediment = extrude_polygon(pediment_profile, pediment_depth)
        pediment = rotate_x(pediment, 90)
        pediment = translate(
            pediment,
            y=-d / 2 - pediment_depth / 2 + BOOLEAN_EMBED,
            z=total_h + entablature_h - BOOLEAN_EMBED,
        )
        additions.append(pediment)

        # Columns on front facade
        col_w = max(profile.min_column_width, 0.5)
        num_cols = 4
        col_spacing = w / (num_cols + 1)
        col_h = total_h * 0.9

        for i in range(num_cols):
            x_pos = -w / 2 + col_spacing * (i + 1)
            if profile.use_window_frames:
                col = round_column(col_w / 2, col_h)
            else:
                col = square_column(col_w, col_h)
            col = translate(col, x=x_pos, y=-d / 2 - col_w / 2 + BOOLEAN_EMBED)
            additions.append(col)

        # Cornice (small overhang at top)
        cornice = box(w + 0.6, d + 0.6, 0.15)
        cornice = translate(cornice, z=total_h + entablature_h - BOOLEAN_EMBED - 0.05)
        additions.append(cornice)

        return assemble_building(shell, cutouts, additions)

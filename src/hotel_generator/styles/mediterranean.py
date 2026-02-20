"""Mediterranean style: barrel/hip roof, arched windows, thick walls."""

from __future__ import annotations

import random
from typing import Any

from manifold3d import Manifold

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.geometry.primitives import box, BOOLEAN_EMBED, BOOLEAN_OVERSHOOT
from hotel_generator.geometry.transforms import translate
from hotel_generator.components.massing import rect_mass
from hotel_generator.components.roof import barrel_roof, hipped_roof
from hotel_generator.components.facade import window_grid_cutouts
from hotel_generator.components.door import door_cutout
from hotel_generator.components.scale import ScaleContext
from hotel_generator.styles.base import HotelStyle, register_style, assemble_building


@register_style
class MediterraneanStyle(HotelStyle):
    @property
    def name(self) -> str:
        return "mediterranean"

    @property
    def display_name(self) -> str:
        return "Mediterranean"

    @property
    def description(self) -> str:
        return "Barrel or hip roof with deep eaves, thick walls, and arched windows"

    def preferred_layout_strategy(self) -> str:
        return "courtyard"

    def generate(self, params: BuildingParams, profile: PrinterProfile) -> Manifold:
        rng = random.Random(params.seed)
        w = params.width
        d = params.depth
        num_floors = max(params.num_floors, 4)
        fh = params.floor_height
        wall_t = profile.min_wall_thickness
        total_h = num_floors * fh

        sc = ScaleContext(w, d, fh, num_floors, profile)

        shell = rect_mass(w, d, total_h)

        cutouts = []
        win_w = sc.window_width
        win_h = sc.window_height
        wins_per_floor = sc.windows_per_floor(w)

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

        # Arched entrance
        door_w = sc.door_width
        door_h = sc.door_height
        door = door_cutout(door_w, door_h, wall_t)
        cutouts.append(translate(door, y=-d / 2))

        # Additions
        additions = []

        # Barrel roof with deep eaves
        eave_ovh = sc.eave_overhang
        roof_w = w + 2 * eave_ovh
        roof_d = d + 2 * eave_ovh
        roof_h = fh * 0.8

        roof = barrel_roof(roof_w, roof_d, roof_h)
        roof = translate(roof, z=total_h - BOOLEAN_EMBED)
        additions.append(roof)

        # Loggia (recessed porch) on ground floor — simplified as a canopy
        loggia_w = w * 0.5
        loggia_d = sc.loggia_depth
        loggia_h = sc.cornice_height
        loggia = box(loggia_w, loggia_d, loggia_h)
        loggia = translate(
            loggia,
            y=-d / 2 - loggia_d / 2 + BOOLEAN_EMBED,
            z=fh - loggia_h,
        )
        additions.append(loggia)

        return assemble_building(shell, cutouts, additions)

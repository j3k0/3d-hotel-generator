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

    def generate(self, params: BuildingParams, profile: PrinterProfile) -> Manifold:
        rng = random.Random(params.seed)
        w = params.width
        d = params.depth
        num_floors = params.num_floors
        fh = params.floor_height
        wall_t = max(profile.min_wall_thickness, 0.8)  # thick walls
        total_h = num_floors * fh

        shell = rect_mass(w, d, total_h)

        cutouts = []
        win_w = 0.4
        win_h = 0.5
        wins_per_floor = max(2, int(w / 2.0))

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
        door_w = max(0.8, w * 0.12)
        door_h = fh * 0.9
        door = door_cutout(door_w, door_h, wall_t)
        cutouts.append(translate(door, y=-d / 2))

        # Additions
        additions = []

        # Barrel roof with deep eaves
        eave_overhang = 0.6
        roof_w = w + 2 * eave_overhang
        roof_d = d + 2 * eave_overhang
        roof_h = fh * 0.8

        roof = barrel_roof(roof_w, roof_d, roof_h)
        roof = translate(roof, z=total_h - BOOLEAN_EMBED)
        additions.append(roof)

        # Loggia (recessed porch) on ground floor — simplified as a canopy
        loggia_w = w * 0.5
        loggia_d = 0.4
        loggia_h = 0.2
        loggia = box(loggia_w, loggia_d, loggia_h)
        loggia = translate(
            loggia,
            y=-d / 2 - loggia_d / 2 + BOOLEAN_EMBED,
            z=fh - loggia_h,
        )
        additions.append(loggia)

        return assemble_building(shell, cutouts, additions)

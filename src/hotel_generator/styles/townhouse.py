"""Townhouse style: narrow rectangle, mansard roof, stoop, bay window."""

from __future__ import annotations

import random
from typing import Any

from manifold3d import Manifold

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.geometry.primitives import box, BOOLEAN_EMBED, BOOLEAN_OVERSHOOT
from hotel_generator.geometry.transforms import translate
from hotel_generator.components.massing import rect_mass
from hotel_generator.components.roof import mansard_roof
from hotel_generator.components.facade import window_grid_cutouts
from hotel_generator.components.door import door_cutout
from hotel_generator.components.scale import ScaleContext
from hotel_generator.styles.base import HotelStyle, register_style, assemble_building


@register_style
class TownhouseStyle(HotelStyle):
    @property
    def name(self) -> str:
        return "townhouse"

    @property
    def display_name(self) -> str:
        return "Townhouse"

    @property
    def description(self) -> str:
        return "Narrow and tall with mansard roof, front stoop, and bay window"

    def preferred_layout_strategy(self) -> str:
        return "row"

    def generate(self, params: BuildingParams, profile: PrinterProfile) -> Manifold:
        rng = random.Random(params.seed)
        w = params.width
        d = params.depth
        num_floors = max(params.num_floors, 3)
        fh = params.floor_height
        wall_t = profile.min_wall_thickness
        total_h = num_floors * fh

        sc = ScaleContext(w, d, fh, num_floors, profile)

        shell = rect_mass(w, d, total_h)

        cutouts = []
        win_w = sc.window_width
        win_h = sc.window_height
        wins_per_floor = sc.windows_per_floor(w)

        # Front and back windows
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

        # Door
        door_w = sc.door_width
        door_h = sc.door_height
        door = door_cutout(door_w, door_h, wall_t)
        cutouts.append(translate(door, x=-w / 4, y=-d / 2))

        # Additions
        additions = []

        # Mansard roof
        ovh = sc.roof_overhang
        roof = mansard_roof(w + 2 * ovh, d + 2 * ovh, fh * 0.6, fh * 0.4, inset=sc.mansard_inset)
        roof = translate(roof, z=total_h - BOOLEAN_EMBED)
        additions.append(roof)

        # Front stoop (2-3 steps)
        num_steps = 3
        step_h = sc.stoop_step_height
        step_d = sc.stoop_step_depth
        stoop_w = door_w + sc.column_width * 2
        for i in range(num_steps):
            step = box(stoop_w, step_d, step_h)
            step = translate(
                step,
                x=-w / 4,
                y=-d / 2 - step_d * (i + 0.5) + BOOLEAN_EMBED,
                z=-step_h * i,
            )
            additions.append(step)

        # Bay window (protruding box on front facade, upper floors)
        bay_w = w * 0.35
        bay_d = sc.bay_depth
        bay_h = fh * (num_floors - 1)  # all but ground floor
        bay = box(bay_w, bay_d, bay_h)
        bay = translate(
            bay,
            x=w / 4,
            y=-d / 2 - bay_d / 2 + BOOLEAN_EMBED,
            z=fh,
        )
        additions.append(bay)

        # Cornice with chamfer-like overhang at roofline
        cornice_h = sc.cornice_height
        cornice = box(w + 2 * ovh, d + 2 * ovh, cornice_h)
        cornice = translate(cornice, z=total_h - cornice_h * 0.5)
        additions.append(cornice)

        return assemble_building(shell, cutouts, additions)

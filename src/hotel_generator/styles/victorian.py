"""Victorian style: asymmetric L-plan, turret, bay windows, complex roofline."""

from __future__ import annotations

import random
from typing import Any

from manifold3d import Manifold

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.geometry.primitives import (
    box,
    cylinder,
    cone,
    BOOLEAN_EMBED,
    BOOLEAN_OVERSHOOT,
)
from hotel_generator.geometry.transforms import translate
from hotel_generator.geometry.booleans import union_all
from hotel_generator.components.massing import l_shape_mass
from hotel_generator.components.roof import gabled_roof, hipped_roof
from hotel_generator.components.facade import window_grid_cutouts
from hotel_generator.components.door import door_cutout
from hotel_generator.components.scale import ScaleContext
from hotel_generator.styles.base import HotelStyle, register_style, assemble_building


@register_style
class VictorianStyle(HotelStyle):
    @property
    def name(self) -> str:
        return "victorian"

    @property
    def display_name(self) -> str:
        return "Victorian"

    @property
    def description(self) -> str:
        return "Asymmetric L-plan with round turret, bay windows, and complex gabled roofline"

    def generate(self, params: BuildingParams, profile: PrinterProfile) -> Manifold:
        rng = random.Random(params.seed)
        w = params.width
        d = params.depth
        num_floors = max(params.num_floors, 3)
        fh = params.floor_height
        wall_t = profile.min_wall_thickness
        total_h = num_floors * fh

        sc = ScaleContext(w, d, fh, num_floors, profile)

        # L-shaped plan
        wing_w = w * 0.45
        wing_d = d * 0.55
        shell = l_shape_mass(w, d, total_h, wing_width=wing_w, wing_depth=wing_d)

        cutouts = []
        win_w = sc.window_width
        win_h = sc.window_height
        wins_per_floor = sc.windows_per_floor(w)

        # Main block windows (front/back)
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
        cutouts.append(translate(door, y=-d / 2))

        # Additions
        additions = []

        # Round turret at the L-junction — prominent feature
        turret_r = sc.turret_radius
        turret_h = total_h + fh * 0.8  # taller than main building
        turret = cylinder(turret_r, turret_h)
        turret_x = w / 2 - wing_w / 2
        turret_y = d / 2 - wing_d * 0.1
        turret = translate(turret, x=turret_x, y=turret_y)
        additions.append(turret)

        # Conical turret cap — tall and pointed
        cap_h = fh * 1.2
        cap = cone(turret_r + sc.roof_overhang * 0.5, 0.0, cap_h)
        cap = translate(cap, x=turret_x, y=turret_y, z=turret_h - BOOLEAN_EMBED)
        additions.append(cap)

        # Main gabled roof
        ovh = sc.roof_overhang
        roof = gabled_roof(w + 2 * ovh, d + 2 * ovh, fh * 0.8)
        roof = translate(roof, z=total_h - BOOLEAN_EMBED)
        additions.append(roof)

        # Wing gabled roof (perpendicular)
        from hotel_generator.geometry.transforms import rotate_z
        wing_roof = gabled_roof(wing_d + 2 * ovh, wing_w + 2 * ovh, fh * 0.7)
        wing_roof = rotate_z(wing_roof, 90)
        wing_roof = translate(
            wing_roof,
            x=(w - wing_w) / 2,
            y=(d + wing_d) / 2 - wing_d * 0.3,
            z=total_h - BOOLEAN_EMBED,
        )
        additions.append(wing_roof)

        # Bay windows on front facade (protruding boxes)
        bay_w = w * 0.2
        bay_d = sc.bay_depth
        bay_h = fh * (num_floors - 1)
        bay = box(bay_w, bay_d, bay_h)
        bay = translate(
            bay,
            x=-w / 4,
            y=-d / 2 - bay_d / 2 + BOOLEAN_EMBED,
            z=fh,
        )
        additions.append(bay)

        return assemble_building(shell, cutouts, additions)

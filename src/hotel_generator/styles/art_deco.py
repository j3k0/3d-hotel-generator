"""Art Deco style: stepped ziggurat, vertical fins, geometric crown."""

from __future__ import annotations

import random
from typing import Any

from manifold3d import Manifold

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.geometry.primitives import box, BOOLEAN_EMBED, BOOLEAN_OVERSHOOT
from hotel_generator.geometry.transforms import translate
from hotel_generator.components.massing import stepped_mass
from hotel_generator.components.roof import flat_roof
from hotel_generator.components.facade import window_grid_cutouts
from hotel_generator.components.door import door_cutout
from hotel_generator.components.scale import ScaleContext
from hotel_generator.styles.base import HotelStyle, register_style, assemble_building


@register_style
class ArtDecoStyle(HotelStyle):
    @property
    def name(self) -> str:
        return "art_deco"

    @property
    def display_name(self) -> str:
        return "Art Deco"

    @property
    def description(self) -> str:
        return "Stepped ziggurat profile with vertical fins and geometric crown"

    def generate(self, params: BuildingParams, profile: PrinterProfile) -> Manifold:
        rng = random.Random(params.seed)
        w = params.width
        d = params.depth
        num_floors = params.num_floors
        fh = params.floor_height
        wall_t = profile.min_wall_thickness

        sc = ScaleContext(w, d, fh, num_floors, profile)

        # Stepped massing (3 tiers)
        num_tiers = 3
        tier_floors = max(1, num_floors // num_tiers)
        tier_h = tier_floors * fh
        setback = sc.setback

        shell = stepped_mass(w, d, num_tiers, tier_h, setback)

        # Windows on each tier
        cutouts = []
        win_w = sc.window_width
        win_h = sc.window_height

        for tier in range(num_tiers):
            tier_w = w - 2 * setback * tier
            tier_d = d - 2 * setback * tier
            tier_base_z = tier * tier_h
            tier_wins = sc.windows_per_floor(tier_w)

            # Front and back windows for this tier
            for y_sign in [-1, 1]:
                cuts = window_grid_cutouts(
                    wall_width=tier_w,
                    wall_height=tier_h,
                    wall_thickness=wall_t,
                    num_floors=tier_floors,
                    floor_height=fh,
                    windows_per_floor=tier_wins,
                    window_width=win_w,
                    window_height=win_h,
                    ground_floor_skip=(tier == 0),
                )
                for c in cuts:
                    cutouts.append(translate(c, y=y_sign * tier_d / 2, z=tier_base_z))

        # Door
        door_w = sc.door_width
        door_h = sc.door_height
        door = door_cutout(door_w, door_h, wall_t)
        cutouts.append(translate(door, y=-d / 2))

        # Additions
        additions = []
        total_h = num_tiers * tier_h

        # Vertical fins on the front facade (base tier)
        fin_t = sc.fin_thickness
        fin_d = sc.fin_depth
        num_fins = 4
        fin_spacing = w / (num_fins + 1)
        for i in range(num_fins):
            fin = box(fin_t, fin_d, total_h * 0.7)
            x_pos = -w / 2 + fin_spacing * (i + 1)
            fin = translate(fin, x=x_pos, y=-d / 2 - fin_d / 2 + BOOLEAN_EMBED)
            additions.append(fin)

        # Geometric crown at top
        crown_w = (w - 2 * setback * (num_tiers - 1)) * 0.5
        crown_d = (d - 2 * setback * (num_tiers - 1)) * 0.5
        crown_h = fh * 0.5
        crown = box(crown_w, crown_d, crown_h)
        crown = translate(crown, z=total_h - BOOLEAN_EMBED)
        additions.append(crown)

        # Small spire on top of crown
        spire_w = crown_w * 0.3
        spire_h = fh * 0.6
        spire = box(spire_w, spire_w, spire_h)
        spire = translate(spire, z=total_h + crown_h - BOOLEAN_EMBED)
        additions.append(spire)

        return assemble_building(shell, cutouts, additions)

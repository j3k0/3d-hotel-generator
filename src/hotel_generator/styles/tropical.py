"""Tropical style: deep overhangs, raised on stilts, multi-tier roof."""

from __future__ import annotations

import random
from typing import Any

from manifold3d import Manifold

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.geometry.primitives import box, BOOLEAN_EMBED, BOOLEAN_OVERSHOOT
from hotel_generator.geometry.transforms import translate
from hotel_generator.components.massing import rect_mass
from hotel_generator.components.roof import hipped_roof, pagoda_roof
from hotel_generator.components.facade import window_grid_cutouts
from hotel_generator.components.column import square_column
from hotel_generator.components.scale import ScaleContext
from hotel_generator.styles.base import HotelStyle, register_style, assemble_building
from hotel_generator.geometry.booleans import union_all


@register_style
class TropicalStyle(HotelStyle):
    @property
    def name(self) -> str:
        return "tropical"

    @property
    def display_name(self) -> str:
        return "Tropical"

    @property
    def description(self) -> str:
        return "Deep overhanging eaves with supports, raised on stilts, multi-tier roof"

    def preferred_layout_strategy(self) -> str:
        return "cluster"

    def generate(self, params: BuildingParams, profile: PrinterProfile) -> Manifold:
        rng = random.Random(params.seed)
        w = params.width
        d = params.depth
        num_floors = max(params.num_floors, 5)
        fh = params.floor_height
        wall_t = profile.min_wall_thickness

        sc = ScaleContext(w, d, fh, num_floors, profile)

        # Raised on stilts: ground level is open
        stilt_h = fh  # one floor of stilts
        building_floors = num_floors - 1
        building_h = building_floors * fh

        # Building body raised above stilts
        shell = rect_mass(w, d, building_h)
        shell = translate(shell, z=stilt_h)

        cutouts = []
        win_w = sc.window_width
        win_h = sc.window_height
        wins_per_floor = sc.windows_per_floor(w)

        for y_sign in [-1, 1]:
            cuts = window_grid_cutouts(
                wall_width=w,
                wall_height=building_h,
                wall_thickness=wall_t,
                num_floors=building_floors,
                floor_height=fh,
                windows_per_floor=wins_per_floor,
                window_width=win_w,
                window_height=win_h,
                ground_floor_skip=False,
            )
            for c in cuts:
                cutouts.append(translate(c, y=y_sign * d / 2, z=stilt_h))

        # Additions
        additions = []
        total_h = stilt_h + building_h

        # Stilts (columns at corners and midpoints)
        col_w = sc.column_width
        stilt_positions = [
            (-w / 2 + col_w, -d / 2 + col_w),
            (w / 2 - col_w, -d / 2 + col_w),
            (-w / 2 + col_w, d / 2 - col_w),
            (w / 2 - col_w, d / 2 - col_w),
            (0, -d / 2 + col_w),
            (0, d / 2 - col_w),
        ]
        for x, y in stilt_positions:
            col = square_column(col_w, stilt_h + BOOLEAN_EMBED)
            col = translate(col, x=x, y=y)
            additions.append(col)

        # Pagoda-style multi-tier roof — distinctive Japanese/East Asian silhouette
        overhang = sc.eave_overhang * 1.5
        roof_h = fh * 0.9
        roof = pagoda_roof(
            w, d,
            tier_height=roof_h,
            num_tiers=3,
            overhang=overhang,
            tier_shrink=0.72,
        )
        roof = translate(roof, z=total_h - BOOLEAN_EMBED)
        additions.append(roof)

        # Overhang support brackets (45-degree, under the eaves)
        from hotel_generator.geometry.primitives import extrude_polygon
        bracket_size = overhang * 0.7
        bracket_thickness = sc.fin_thickness
        bracket_profile = [
            (0, 0),
            (bracket_size, 0),
            (0, bracket_size),
        ]
        # Front brackets
        for x_offset in [-w / 3, 0, w / 3]:
            bracket = extrude_polygon(bracket_profile, bracket_thickness)
            bracket = translate(
                bracket,
                x=x_offset - bracket_thickness / 2,
                y=-d / 2 - bracket_size + BOOLEAN_EMBED,
                z=total_h - bracket_size,
            )
            additions.append(bracket)

        return assemble_building(shell, cutouts, additions)

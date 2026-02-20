"""Skyscraper style: tall tower on podium, curtain wall grid, crown."""

from __future__ import annotations

import random
from typing import Any

from manifold3d import Manifold

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.geometry.primitives import box, BOOLEAN_EMBED, BOOLEAN_OVERSHOOT
from hotel_generator.geometry.transforms import translate
from hotel_generator.components.massing import podium_tower_mass
from hotel_generator.components.roof import flat_roof
from hotel_generator.components.facade import window_grid_cutouts
from hotel_generator.components.door import door_cutout
from hotel_generator.components.scale import ScaleContext
from hotel_generator.styles.base import HotelStyle, register_style, assemble_building


@register_style
class SkyscraperStyle(HotelStyle):
    @property
    def name(self) -> str:
        return "skyscraper"

    @property
    def display_name(self) -> str:
        return "Skyscraper"

    @property
    def description(self) -> str:
        return "Tall slender tower on a wider podium base with crown element"

    def preferred_layout_strategy(self) -> str:
        return "hierarchical"

    def generate(self, params: BuildingParams, profile: PrinterProfile) -> Manifold:
        rng = random.Random(params.seed)
        w = params.width
        d = params.depth
        num_floors = max(params.num_floors, 8)  # Skyscrapers need real height
        fh = params.floor_height
        wall_t = profile.min_wall_thickness

        sc = ScaleContext(w, d, fh, num_floors, profile)

        # Podium: 2 floors, full width — wide rectangular base
        podium_floors = 2
        podium_h = podium_floors * fh

        # Tower: significantly narrower and taller — the defining skyscraper feature
        tower_w = w * 0.45
        tower_d = d * 0.50
        tower_floors = num_floors - podium_floors
        tower_h = tower_floors * fh

        shell = podium_tower_mass(w, d, podium_h, tower_w, tower_d, tower_h)

        cutouts = []

        # Podium windows
        podium_wins = sc.windows_per_floor(w)
        podium_win_w = sc.window_width
        podium_win_h = sc.window_height
        for y_sign in [-1, 1]:
            cuts = window_grid_cutouts(
                wall_width=w,
                wall_height=podium_h,
                wall_thickness=wall_t,
                num_floors=podium_floors,
                floor_height=fh,
                windows_per_floor=podium_wins,
                window_width=podium_win_w,
                window_height=podium_win_h,
                ground_floor_skip=True,
            )
            for c in cuts:
                cutouts.append(translate(c, y=y_sign * d / 2))

        # Podium side windows
        from hotel_generator.geometry.transforms import rotate_z
        podium_side_wins = sc.windows_per_floor(d)
        for x_sign in [-1, 1]:
            cuts = window_grid_cutouts(
                wall_width=d,
                wall_height=podium_h,
                wall_thickness=wall_t,
                num_floors=podium_floors,
                floor_height=fh,
                windows_per_floor=podium_side_wins,
                window_width=podium_win_w,
                window_height=podium_win_h,
                ground_floor_skip=True,
            )
            for c in cuts:
                rotated = rotate_z(c, 90)
                cutouts.append(translate(rotated, x=x_sign * w / 2))

        # Tower windows (dense grid = curtain wall)
        tower_sc = ScaleContext(tower_w, tower_d, fh, tower_floors, profile)
        tower_wins = tower_sc.windows_per_floor(tower_w)
        tower_win_w = sc.window_width * 0.6  # narrow curtain wall strips
        tower_win_h = sc.window_height
        for y_sign in [-1, 1]:
            cuts = window_grid_cutouts(
                wall_width=tower_w,
                wall_height=tower_h,
                wall_thickness=wall_t,
                num_floors=tower_floors,
                floor_height=fh,
                windows_per_floor=tower_wins,
                window_width=tower_win_w,
                window_height=tower_win_h,
                ground_floor_skip=False,
            )
            for c in cuts:
                cutouts.append(translate(c, y=y_sign * tower_d / 2, z=podium_h))

        # Side tower windows
        tower_side_wins = tower_sc.windows_per_floor(tower_d)
        for x_sign in [-1, 1]:
            cuts = window_grid_cutouts(
                wall_width=tower_d,
                wall_height=tower_h,
                wall_thickness=wall_t,
                num_floors=tower_floors,
                floor_height=fh,
                windows_per_floor=tower_side_wins,
                window_width=tower_win_w,
                window_height=tower_win_h,
                ground_floor_skip=False,
            )
            for c in cuts:
                rotated = rotate_z(c, 90)
                cutouts.append(translate(rotated, x=x_sign * tower_w / 2, z=podium_h))

        # Door on podium
        door_w = sc.door_width
        door_h = sc.door_height
        door = door_cutout(door_w, door_h, wall_t)
        cutouts.append(translate(door, y=-d / 2))

        # Additions
        additions = []
        total_h = podium_h + tower_h

        # Crown element at top of tower — stepped back for dramatic profile
        crown_w = tower_w * 0.65
        crown_d = tower_d * 0.65
        crown_h = fh * 0.8
        crown = box(crown_w, crown_d, crown_h)
        crown = translate(crown, z=total_h - BOOLEAN_EMBED)
        additions.append(crown)

        # Antenna/spire — tall and slender for iconic silhouette
        spire_w = crown_w * 0.15
        spire_h = fh * 2.0
        spire = box(spire_w, spire_w, spire_h)
        spire = translate(spire, z=total_h + crown_h - BOOLEAN_EMBED)
        additions.append(spire)

        return assemble_building(shell, cutouts, additions)

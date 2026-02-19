"""Modern architectural style: flat roof, grid windows, optional cantilever."""

from __future__ import annotations

import random
from typing import Any

from manifold3d import Manifold

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.errors import InvalidParamsError
from hotel_generator.geometry.primitives import box, BOOLEAN_OVERSHOOT, BOOLEAN_EMBED
from hotel_generator.geometry.transforms import translate
from hotel_generator.components.massing import rect_mass
from hotel_generator.components.roof import flat_roof
from hotel_generator.components.facade import window_grid_cutouts
from hotel_generator.components.door import door_cutout
from hotel_generator.styles.base import HotelStyle, register_style, assemble_building


@register_style
class ModernStyle(HotelStyle):
    """Modern style: clean lines, flat roof, horizontal window bands."""

    @property
    def name(self) -> str:
        return "modern"

    @property
    def display_name(self) -> str:
        return "Modern"

    @property
    def description(self) -> str:
        return "Clean rectangular geometry with flat roof, horizontal window bands, and optional penthouse"

    def style_params_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "has_penthouse": {
                    "type": "boolean",
                    "default": True,
                    "description": "Add a setback penthouse on top",
                },
                "has_cantilever": {
                    "type": "boolean",
                    "default": False,
                    "description": "Add a cantilevered upper section",
                },
                "window_style": {
                    "type": "string",
                    "enum": ["grid", "band"],
                    "default": "grid",
                    "description": "Window layout style",
                },
            },
        }

    def validate_style_params(self, params: dict[str, Any]) -> dict[str, Any]:
        defaults = {
            "has_penthouse": True,
            "has_cantilever": False,
            "window_style": "grid",
        }
        result = {**defaults, **params}
        if result["window_style"] not in ("grid", "band"):
            raise InvalidParamsError(
                f"window_style must be 'grid' or 'band', got '{result['window_style']}'"
            )
        return result

    def generate(
        self,
        params: BuildingParams,
        profile: PrinterProfile,
    ) -> Manifold:
        rng = random.Random(params.seed)

        style_p = self.validate_style_params(params.style_params)
        w = params.width
        d = params.depth
        num_floors = params.num_floors
        fh = params.floor_height
        wall_t = profile.min_wall_thickness

        total_h = num_floors * fh

        # Main building shell
        shell = rect_mass(w, d, total_h)

        # Window cutouts on front and back facades
        win_w = 0.4
        win_h = 0.5
        windows_per_floor = max(2, int(w / 1.5))

        cutouts = []

        # Front facade windows (at -depth/2)
        front_cuts = window_grid_cutouts(
            wall_width=w,
            wall_height=total_h,
            wall_thickness=wall_t,
            num_floors=num_floors,
            floor_height=fh,
            windows_per_floor=windows_per_floor,
            window_width=win_w,
            window_height=win_h,
        )
        for c in front_cuts:
            cutouts.append(translate(c, y=-d / 2))

        # Back facade windows (at +depth/2)
        back_cuts = window_grid_cutouts(
            wall_width=w,
            wall_height=total_h,
            wall_thickness=wall_t,
            num_floors=num_floors,
            floor_height=fh,
            windows_per_floor=windows_per_floor,
            window_width=win_w,
            window_height=win_h,
        )
        for c in back_cuts:
            cutouts.append(translate(c, y=d / 2))

        # Side windows (fewer per floor)
        side_wins = max(1, int(d / 2.0))
        for side_y_sign in [-1, 1]:
            side_cuts = window_grid_cutouts(
                wall_width=d,
                wall_height=total_h,
                wall_thickness=wall_t,
                num_floors=num_floors,
                floor_height=fh,
                windows_per_floor=side_wins,
                window_width=win_w,
                window_height=win_h,
            )
            for c in side_cuts:
                # Rotate side windows 90 degrees and position on left/right wall
                from hotel_generator.geometry.transforms import rotate_z
                rotated = rotate_z(c, 90)
                cutouts.append(translate(rotated, x=side_y_sign * w / 2))

        # Door cutout on front facade
        door_w = max(0.8, w * 0.12)
        door_h = fh * 0.85
        door = door_cutout(door_w, door_h, wall_t)
        cutouts.append(translate(door, y=-d / 2))

        # Additions
        additions = []

        # Flat roof with parapet
        roof = flat_roof(w + 0.2, d + 0.2, parapet_height=0.3, slab_thickness=0.2)
        roof = translate(roof, z=total_h - BOOLEAN_EMBED)
        additions.append(roof)

        # Optional penthouse (smaller box on top)
        if style_p["has_penthouse"]:
            ph_w = w * 0.6
            ph_d = d * 0.6
            ph_h = fh * 0.8
            penthouse = box(ph_w, ph_d, ph_h)
            penthouse = translate(penthouse, z=total_h + 0.2 - BOOLEAN_EMBED)
            additions.append(penthouse)

            # Penthouse roof
            ph_roof = flat_roof(ph_w + 0.1, ph_d + 0.1, parapet_height=0.15, slab_thickness=0.15)
            ph_roof = translate(ph_roof, z=total_h + 0.2 + ph_h - BOOLEAN_EMBED)
            additions.append(ph_roof)

        # Optional cantilever
        if style_p["has_cantilever"]:
            cant_h = fh * 2
            cant_d = d * 0.15
            cantilever = box(w, cant_d, cant_h)
            cantilever = translate(
                cantilever,
                y=-d / 2 - cant_d / 2 + BOOLEAN_EMBED,
                z=total_h - cant_h,
            )
            additions.append(cantilever)

        return assemble_building(shell, cutouts, additions)

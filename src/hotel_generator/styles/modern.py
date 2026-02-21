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
from hotel_generator.components.scale import ScaleContext
from hotel_generator.styles.base import GardenTheme, HotelStyle, register_style, assemble_building


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

    def preferred_layout_strategy(self) -> str:
        return "campus"

    def garden_theme(self) -> GardenTheme:
        return GardenTheme(
            tree_type="deciduous",
            tree_density=0.3,
            pool_shape="rectangular",
            pool_size="medium",
            has_hedges=True,
            hedge_style="sparse",
            has_terrace=True,
            path_style="straight",
        )

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
        num_floors = max(params.num_floors, 5)
        fh = params.floor_height
        wall_t = profile.min_wall_thickness

        sc = ScaleContext(w, d, fh, num_floors, profile)
        total_h = num_floors * fh

        # Main building shell
        shell = rect_mass(w, d, total_h)

        # Window cutouts on front and back facades
        win_w = sc.window_width
        win_h = sc.window_height
        windows_per_floor = sc.windows_per_floor(w)

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
        side_wins = sc.windows_per_floor(d)
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
                from hotel_generator.geometry.transforms import rotate_z
                rotated = rotate_z(c, 90)
                cutouts.append(translate(rotated, x=side_y_sign * w / 2))

        # Door cutout on front facade
        door_w = sc.door_width
        door_h = sc.door_height
        door = door_cutout(door_w, door_h, wall_t)
        cutouts.append(translate(door, y=-d / 2))

        # Additions
        additions = []

        # Flat roof with parapet
        ovh = sc.roof_overhang
        roof = flat_roof(
            w + 2 * ovh, d + 2 * ovh,
            parapet_height=sc.parapet_height,
            slab_thickness=sc.roof_slab_thickness,
            parapet_wall_thickness=sc.parapet_wall_thickness,
        )
        roof = translate(roof, z=total_h - BOOLEAN_EMBED)
        additions.append(roof)

        # Optional penthouse (smaller box on top)
        if style_p["has_penthouse"]:
            ph_w = w * 0.6
            ph_d = d * 0.6
            ph_h = fh * 0.8
            penthouse = box(ph_w, ph_d, ph_h)
            penthouse = translate(penthouse, z=total_h + sc.roof_slab_thickness - BOOLEAN_EMBED)
            additions.append(penthouse)

            # Penthouse roof
            ph_roof = flat_roof(
                ph_w + ovh, ph_d + ovh,
                parapet_height=sc.parapet_height * 0.5,
                slab_thickness=sc.roof_slab_thickness * 0.75,
                parapet_wall_thickness=sc.parapet_wall_thickness,
            )
            ph_roof = translate(ph_roof, z=total_h + sc.roof_slab_thickness + ph_h - BOOLEAN_EMBED)
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

"""PropertyBuilder: generates a single property plate with buildings, garden, and road strip."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any

from manifold3d import Manifold

from hotel_generator.assembly.building import BuildResult
from hotel_generator.board.config import GardenFeaturePlacement, PropertyParams
from hotel_generator.board.garden_layout import GardenLayoutEngine
from hotel_generator.complex.builder import ComplexBuilder, ComplexResult
from hotel_generator.components.base import base_slab
from hotel_generator.components.landscape import (
    conifer_tree,
    deciduous_tree,
    garden_path,
    hedge_row,
    palm_tree,
    swimming_pool,
    terrace,
)
from hotel_generator.config import BuildingPlacement, ComplexParams, PrinterProfile
from hotel_generator.errors import GeometryError
from hotel_generator.geometry.booleans import compose_disjoint, difference_all, union_all
from hotel_generator.geometry.primitives import BOOLEAN_EMBED, BOOLEAN_OVERSHOOT, box
from hotel_generator.geometry.transforms import rotate_z, translate
from hotel_generator.settings import Settings
from hotel_generator.styles.base import STYLE_REGISTRY


@dataclass
class PropertyResult:
    """Result of building one property plate."""

    plate: Manifold  # Combined plate (base + buildings + garden)
    base_plate: Manifold  # Base plate with road strip (without buildings/garden)
    buildings: list[BuildResult]
    garden_features: Manifold  # All garden geometry combined
    placements: list[BuildingPlacement]
    garden_placements: list[GardenFeaturePlacement]
    lot_width: float
    lot_depth: float
    metadata: dict[str, Any] = field(default_factory=dict)


class PropertyBuilder:
    """Generates a single property plate: base + road + buildings + garden."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.complex_builder = ComplexBuilder(settings)
        self.garden_engine = GardenLayoutEngine()

    def build(self, params: PropertyParams) -> PropertyResult:
        """Build a property plate.

        Coordinate system:
        - Lot centered on X: x ∈ [-lot_width/2, lot_width/2]
        - Lot extends from y=0 to y=lot_depth
        - Road strip at y=0 to y=road_width (south edge)
        - Buildings in center zone
        - Garden fills remaining space
        """
        start_time = time.time()
        rng = random.Random(params.seed)
        profile = PrinterProfile.from_type(params.printer_type)

        lot_w = params.lot_width
        lot_d = params.lot_depth
        road_w = params.road_width

        # --- 1. Create base plate ---
        plate = base_slab(lot_w, lot_d, profile.base_thickness, profile.base_chamfer)
        # base_slab is centered on X/Y with top at Z=0.
        # Shift so it spans x=[-lot_w/2, lot_w/2], y=[0, lot_d]
        plate = translate(plate, y=lot_d / 2)

        # --- 2. Add road strip ---
        road_strip = self._make_road_strip(lot_w, road_w, profile)
        plate = union_all([plate, road_strip])

        # --- 3. Generate building complex ---
        complex_result = self._build_complex(params, profile, lot_w, lot_d, road_w, rng)
        building_placements = complex_result.placements

        # Position complex buildings onto the property plate.
        # Complex is centered at origin; we offset it into the building zone.
        # Place buildings centered in the available depth (between road and far edge)
        available_depth = lot_d - road_w - 4.0
        bldg_zone_y = road_w + 2.0 + available_depth / 2
        positioned_buildings: list[Manifold] = []
        adjusted_placements: list[BuildingPlacement] = []
        for i, (bld, plc) in enumerate(zip(complex_result.buildings, building_placements)):
            # Shift placement into property coordinates
            adj_plc = BuildingPlacement(
                x=plc.x,
                y=plc.y + bldg_zone_y,
                rotation=plc.rotation,
                width=plc.width,
                depth=plc.depth,
                num_floors=plc.num_floors,
                floor_height=plc.floor_height,
                role=plc.role,
            )
            adjusted_placements.append(adj_plc)

            m = bld.manifold
            if plc.rotation != 0:
                m = rotate_z(m, plc.rotation)
            m = translate(m, x=plc.x, y=plc.y + bldg_zone_y)
            positioned_buildings.append(m)

        # --- 4. Compute garden layout ---
        garden_placements: list[GardenFeaturePlacement] = []
        garden_manifold = Manifold()
        pool_recesses: list[Manifold] = []

        if params.garden_enabled:
            # Resolve style name (preset may override the default style_name)
            resolved_style_name = params.style_name
            if params.preset:
                from hotel_generator.complex.presets import get_preset
                resolved_style_name = get_preset(params.preset).style_name
            style = STYLE_REGISTRY.get(
                resolved_style_name,
                list(STYLE_REGISTRY.values())[0] if STYLE_REGISTRY else None,
            )
            theme = style.garden_theme() if style else None
            if theme is not None:
                garden_placements = self.garden_engine.compute_layout(
                    lot_width=lot_w,
                    lot_depth=lot_d,
                    road_edge="south",
                    road_width=road_w,
                    building_placements=adjusted_placements,
                    garden_theme=theme,
                    rng=rng,
                )

                # --- 5. Generate garden geometry ---
                garden_parts: list[Manifold] = []
                for gf in garden_placements:
                    parts = self._generate_garden_feature(gf, rng, profile)
                    if parts is None:
                        continue
                    if isinstance(parts, tuple):
                        # Pool returns (rim, recess)
                        rim, recess = parts
                        if not rim.is_empty():
                            garden_parts.append(rim)
                        if not recess.is_empty():
                            pool_recesses.append(recess)
                    else:
                        if not parts.is_empty():
                            garden_parts.append(parts)

                if garden_parts:
                    garden_manifold = union_all(garden_parts)

        # --- 6. Assemble final plate ---
        # Subtract pool recesses from base plate
        if pool_recesses:
            plate = difference_all(plate, pool_recesses)

        # Union base plate + buildings + garden
        all_parts = [plate]
        all_parts.extend(positioned_buildings)
        if not garden_manifold.is_empty():
            all_parts.append(garden_manifold)
        combined = union_all(all_parts)

        elapsed = time.time() - start_time

        return PropertyResult(
            plate=combined,
            base_plate=plate,
            buildings=complex_result.buildings,
            garden_features=garden_manifold,
            placements=adjusted_placements,
            garden_placements=garden_placements,
            lot_width=lot_w,
            lot_depth=lot_d,
            metadata={
                "style": params.style_name,
                "preset": params.preset,
                "num_buildings": len(complex_result.buildings),
                "num_garden_features": len(garden_placements),
                "generation_time_ms": round(elapsed * 1000),
                "seed": params.seed,
            },
        )

    # ------------------------------------------------------------------
    # Road strip
    # ------------------------------------------------------------------

    def _make_road_strip(
        self,
        lot_width: float,
        road_width: float,
        profile: PrinterProfile,
    ) -> Manifold:
        """Create a road strip along the south edge (y=0 to y=road_width).

        The road is a slightly recessed surface with raised curb lines.
        """
        road_recess = 0.2  # mm below base surface
        curb_height = 0.3  # mm above base surface
        curb_width = 0.8  # mm wide

        # Road surface: a thin slab at slight negative Z
        road_surface = box(lot_width - 1.0, road_width - 2 * curb_width, road_recess)
        road_surface = translate(road_surface, y=road_width / 2, z=-road_recess)

        # Curb lines along both sides of the road
        curb_near = box(lot_width - 1.0, curb_width, curb_height)
        curb_near = translate(curb_near, y=curb_width / 2)
        curb_far = box(lot_width - 1.0, curb_width, curb_height)
        curb_far = translate(curb_far, y=road_width - curb_width / 2)

        return union_all([curb_near, curb_far])

    # ------------------------------------------------------------------
    # Building complex
    # ------------------------------------------------------------------

    def _build_complex(
        self,
        params: PropertyParams,
        profile: PrinterProfile,
        lot_w: float,
        lot_d: float,
        road_w: float,
        rng: random.Random,
    ) -> ComplexResult:
        """Generate the building complex using existing ComplexBuilder.

        We let the ComplexBuilder auto-size the lot rather than constraining it,
        since different layout strategies (cluster, courtyard) need varying space.
        The complex is then positioned within the property plate.
        """
        complex_params = ComplexParams(
            style_name=params.style_name,
            num_buildings=params.num_buildings,
            printer_type=params.printer_type,
            seed=params.seed,
            max_triangles=params.max_triangles,
            style_params=params.style_params,
            building_spacing=params.building_spacing,
            preset=params.preset,
        )

        return self.complex_builder.build(complex_params)

    # ------------------------------------------------------------------
    # Garden feature generation
    # ------------------------------------------------------------------

    def _generate_garden_feature(
        self,
        gf: GardenFeaturePlacement,
        rng: random.Random,
        profile: PrinterProfile,
    ) -> Manifold | tuple[Manifold, Manifold] | None:
        """Generate geometry for a single garden feature and position it."""
        ft = gf.feature_type
        p = gf.params

        if ft == "deciduous_tree":
            m = deciduous_tree(
                height=p.get("height", 4.0),
                canopy_radius=p.get("canopy_radius", 1.5),
                trunk_radius=max(profile.min_wall_thickness / 2, 0.4),
                rng=rng,
            )
            return translate(m, x=gf.x, y=gf.y)

        elif ft == "conifer_tree":
            m = conifer_tree(
                height=p.get("height", 5.0),
                canopy_radius=p.get("canopy_radius", 1.2),
                trunk_radius=max(profile.min_wall_thickness / 2, 0.4),
                rng=rng,
            )
            return translate(m, x=gf.x, y=gf.y)

        elif ft == "palm_tree":
            m = palm_tree(
                height=p.get("height", 6.0),
                trunk_radius=max(profile.min_wall_thickness / 2, 0.4),
                canopy_radius=p.get("canopy_radius", 1.5),
                rng=rng,
            )
            return translate(m, x=gf.x, y=gf.y)

        elif ft == "hedge":
            length = p.get("length", 10.0)
            height = p.get("height", 1.5)
            width = max(p.get("width", 1.0), profile.min_wall_thickness)
            m = hedge_row(length, height, width)
            if gf.rotation != 0:
                m = rotate_z(m, gf.rotation)
            return translate(m, x=gf.x, y=gf.y)

        elif ft == "pool":
            pool_w = p.get("width", 18.0)
            pool_d = p.get("depth", 11.0)
            shape = p.get("shape", "rectangular")
            rim, recess = swimming_pool(
                width=pool_w,
                depth=pool_d,
                pool_depth=0.5,
                rim_width=max(0.8, profile.min_wall_thickness),
                rim_height=0.2,
                shape=shape,
            )
            rim = translate(rim, x=gf.x, y=gf.y)
            recess = translate(recess, x=gf.x, y=gf.y)
            return (rim, recess)

        elif ft == "path":
            points = p.get("points", [])
            if len(points) < 2:
                return None
            pts = [(pt[0], pt[1]) for pt in points]
            m = garden_path(
                pts,
                width=p.get("width", 2.0),
                height=p.get("height", 0.3),
            )
            return m

        elif ft == "terrace":
            m = terrace(
                width=p.get("width", 10.0),
                depth=p.get("depth", 5.0),
                height=p.get("height", 0.5),
            )
            return translate(m, x=gf.x, y=gf.y)

        return None

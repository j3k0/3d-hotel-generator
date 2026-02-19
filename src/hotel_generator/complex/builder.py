"""ComplexBuilder: orchestrates multi-building hotel complex generation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from manifold3d import Manifold

from hotel_generator.assembly.building import HotelBuilder, BuildResult
from hotel_generator.config import BuildingParams, BuildingPlacement, ComplexParams, PrinterProfile
from hotel_generator.complex.base_plate import complex_base_plate
from hotel_generator.errors import InvalidParamsError
from hotel_generator.geometry.booleans import union_all
from hotel_generator.geometry.transforms import translate, rotate_z
from hotel_generator.layout.engine import LayoutEngine
from hotel_generator.layout.placement import compute_lot_bounds
from hotel_generator.settings import Settings
from hotel_generator.styles.base import STYLE_REGISTRY


@dataclass
class ComplexResult:
    """Result of building a hotel complex."""

    buildings: list[BuildResult]
    base_plate: Manifold
    combined: Manifold
    placements: list[BuildingPlacement]
    lot_width: float
    lot_depth: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ComplexBuilder:
    """Orchestrates generation of multi-building hotel complexes."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.hotel_builder = HotelBuilder(settings)
        self.layout_engine = LayoutEngine()

    def build(self, params: ComplexParams) -> ComplexResult:
        """Build a hotel complex.

        1. Resolve style and get preferred layout strategy
        2. Compute layout (placements)
        3. Generate each building (skip individual bases)
        4. Position buildings on the lot
        5. Generate shared base plate
        6. Combine for preview
        """
        start_time = time.time()

        # 1. Resolve style
        if params.style_name not in STYLE_REGISTRY:
            available = sorted(STYLE_REGISTRY.keys())
            raise InvalidParamsError(
                f"Unknown style '{params.style_name}'. "
                f"Available: {', '.join(available)}"
            )
        style = STYLE_REGISTRY[params.style_name]
        profile = PrinterProfile.from_type(params.printer_type)

        # 2. Compute layout
        strategy = style.preferred_layout_strategy()
        placements = self.layout_engine.compute_layout(params, strategy=strategy)

        # 3. Generate each building
        per_building_tris = params.max_triangles // max(1, params.num_buildings)
        buildings: list[BuildResult] = []
        positioned: list[Manifold] = []

        for i, placement in enumerate(placements):
            building_params = BuildingParams(
                style_name=params.style_name,
                width=placement.width,
                depth=placement.depth,
                num_floors=placement.num_floors,
                floor_height=placement.floor_height,
                printer_type=params.printer_type,
                seed=params.seed + i,
                max_triangles=per_building_tris,
                style_params=params.style_params,
            )

            result = self.hotel_builder.build(building_params, skip_base=True)
            buildings.append(result)

            # 4. Position on lot
            m = result.manifold
            if placement.rotation != 0:
                m = rotate_z(m, placement.rotation)
            m = translate(m, x=placement.x, y=placement.y)
            positioned.append(m)

        # 5. Compute lot bounds and generate base plate
        lot_w, lot_d = compute_lot_bounds(placements, margin=profile.base_thickness)
        if params.lot_width is not None:
            lot_w = max(lot_w, params.lot_width)
        if params.lot_depth is not None:
            lot_d = max(lot_d, params.lot_depth)

        base = complex_base_plate(
            lot_width=lot_w,
            lot_depth=lot_d,
            thickness=profile.base_thickness,
            chamfer=profile.base_chamfer,
            placements=placements,
        )

        # 6. Combine for preview
        all_parts = positioned + [base]
        combined = union_all(all_parts)

        elapsed = time.time() - start_time

        return ComplexResult(
            buildings=buildings,
            base_plate=base,
            combined=combined,
            placements=placements,
            lot_width=lot_w,
            lot_depth=lot_d,
            metadata={
                "style": params.style_name,
                "num_buildings": len(buildings),
                "printer_type": params.printer_type,
                "generation_time_ms": round(elapsed * 1000),
                "seed": params.seed,
                "strategy": strategy,
            },
        )

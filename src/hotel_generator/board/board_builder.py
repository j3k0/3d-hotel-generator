"""BoardBuilder: orchestrates generation of all property plates for a game board."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

from hotel_generator.board.config import BoardParams, PropertyParams, PropertySlot
from hotel_generator.board.property_builder import PropertyBuilder, PropertyResult
from hotel_generator.board.road import generate_road_layout
from hotel_generator.settings import Settings


@dataclass
class BoardResult:
    """Result of building a full game board."""

    properties: list[PropertyResult]
    property_slots: list[PropertySlot]
    road_shape: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BoardBuilder:
    """Generates all property plates for a game board."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.property_builder = PropertyBuilder(settings)

    def build(self, params: BoardParams) -> BoardResult:
        """Build a full game board.

        1. Generate road layout (property slots with positions and presets)
        2. For each slot, create PropertyParams and build the plate
        3. Return BoardResult with all plates and layout info
        """
        start_time = time.time()
        rng = random.Random(params.seed)

        # 1. Generate road layout
        slots = generate_road_layout(
            road_shape=params.road_shape,
            num_properties=params.num_properties,
            property_width=params.property_width,
            property_depth=params.property_depth,
            road_width=params.road_width,
            rng=rng,
            style_assignments=params.style_assignments,
        )

        # 2. Build each property
        properties: list[PropertyResult] = []
        for slot in slots:
            prop_params = PropertyParams(
                preset=slot.assigned_preset,
                style_name="modern",  # overridden by preset
                lot_width=params.property_width,
                lot_depth=params.property_depth,
                road_edge=slot.road_edge,
                road_width=params.road_width,
                printer_type=params.printer_type,
                seed=params.seed + slot.index * 100,
                max_triangles=params.max_triangles_per_property,
            )
            result = self.property_builder.build(prop_params)
            properties.append(result)

        elapsed = time.time() - start_time

        return BoardResult(
            properties=properties,
            property_slots=slots,
            road_shape=params.road_shape,
            metadata={
                "num_properties": len(properties),
                "road_shape": params.road_shape,
                "generation_time_ms": round(elapsed * 1000),
                "seed": params.seed,
            },
        )

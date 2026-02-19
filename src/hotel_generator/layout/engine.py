"""Layout engine: dispatches to strategy functions and validates results."""

from __future__ import annotations

import random

from hotel_generator.config import BuildingPlacement, ComplexParams
from hotel_generator.errors import InvalidParamsError
from hotel_generator.layout.placement import any_overlaps, compute_lot_bounds
from hotel_generator.layout.strategies import STRATEGIES


class LayoutEngine:
    """Compute building placements for a hotel complex."""

    def compute_layout(
        self,
        params: ComplexParams,
        strategy: str | None = None,
        roles: list[str] | None = None,
    ) -> list[BuildingPlacement]:
        """Compute placements for a complex.

        If params.placements is provided, validates and returns them.
        Otherwise, uses the specified strategy (or default "row").
        """
        # If explicit placements provided, validate and return
        if params.placements is not None:
            if any_overlaps(params.placements):
                raise InvalidParamsError("Provided placements have overlapping buildings")
            return params.placements

        strategy_name = strategy or "row"
        if strategy_name not in STRATEGIES:
            raise InvalidParamsError(
                f"Unknown layout strategy '{strategy_name}'. "
                f"Valid: {sorted(STRATEGIES.keys())}"
            )

        rng = random.Random(params.seed)
        strategy_fn = STRATEGIES[strategy_name]

        placements = strategy_fn(
            num_buildings=params.num_buildings,
            rng=rng,
            base_width=30.0,  # default base building width
            base_depth=25.0,  # default base building depth
            base_floors=4,
            floor_height=5.0,
            spacing=params.building_spacing,
            roles=roles,
        )

        # Validate no overlaps
        if any_overlaps(placements):
            raise InvalidParamsError(
                f"Layout strategy '{strategy_name}' produced overlapping buildings"
            )

        # Validate lot bounds if specified
        if params.lot_width is not None and params.lot_depth is not None:
            lot_w, lot_d = compute_lot_bounds(placements, margin=0.0)
            if lot_w > params.lot_width or lot_d > params.lot_depth:
                raise InvalidParamsError(
                    f"Buildings don't fit in lot ({lot_w:.1f}x{lot_d:.1f}mm "
                    f"exceeds {params.lot_width}x{params.lot_depth}mm)"
                )

        return placements

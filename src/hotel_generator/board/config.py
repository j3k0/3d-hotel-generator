"""Data models for board-level generation (property plates and game boards)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, model_validator


# ---------------------------------------------------------------------------
# Garden feature placement
# ---------------------------------------------------------------------------

class GardenFeaturePlacement(BaseModel):
    """Position of a single garden feature on the property plate."""

    feature_type: str  # "deciduous_tree", "conifer_tree", "palm_tree",
    #                    "hedge", "pool", "path", "terrace"
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    params: dict[str, Any] = {}  # Feature-specific params (e.g., height, shape)


# ---------------------------------------------------------------------------
# Property params
# ---------------------------------------------------------------------------

VALID_ROAD_EDGES = ("south", "north", "east", "west")


class PropertyParams(BaseModel):
    """Parameters for generating one property plate."""

    preset: str | None = None  # Use existing hotel preset (royal, waikiki, etc.)
    style_name: str = "modern"  # Architectural style
    num_buildings: int = 3
    lot_width: float = 100.0  # mm, total property plate width
    lot_depth: float = 80.0  # mm, total property plate depth
    road_edge: str = "south"  # Which side faces the road
    road_width: float = 8.0  # mm, width of road strip
    garden_enabled: bool = True
    printer_type: str = "fdm"
    seed: int = 42
    style_params: dict[str, Any] = {}
    building_spacing: float = 5.0
    max_triangles: int = 300_000

    @model_validator(mode="after")
    def check_road_edge(self):
        if self.road_edge not in VALID_ROAD_EDGES:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"road_edge must be one of {VALID_ROAD_EDGES}, got '{self.road_edge}'"
            )
        return self

    @model_validator(mode="after")
    def check_printer_type(self):
        if self.printer_type not in ("fdm", "resin"):
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"printer_type must be 'fdm' or 'resin', got '{self.printer_type}'"
            )
        return self

    @model_validator(mode="after")
    def check_lot_dimensions(self):
        if self.lot_width < 40.0 or self.lot_depth < 30.0:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"lot must be at least 40x30mm, got {self.lot_width}x{self.lot_depth}"
            )
        return self


# ---------------------------------------------------------------------------
# Board params
# ---------------------------------------------------------------------------

VALID_ROAD_SHAPES = ("loop", "serpentine", "linear")

DEFAULT_PRESET_ASSIGNMENTS = [
    "royal", "fujiyama", "waikiki", "president",
    "safari", "taj_mahal", "letoile", "boomerang",
]


class BoardParams(BaseModel):
    """Parameters for generating a full game board (all property plates)."""

    road_shape: str = "loop"
    num_properties: int = 8
    property_width: float = 100.0  # mm per property
    property_depth: float = 80.0  # mm per property
    road_width: float = 8.0  # mm
    printer_type: str = "fdm"
    seed: int = 42
    max_triangles_per_property: int = 300_000
    # index → preset name, auto-assigned from DEFAULT_PRESET_ASSIGNMENTS if None
    style_assignments: dict[int, str] | None = None

    @model_validator(mode="after")
    def check_road_shape(self):
        if self.road_shape not in VALID_ROAD_SHAPES:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"road_shape must be one of {VALID_ROAD_SHAPES}, got '{self.road_shape}'"
            )
        return self

    @model_validator(mode="after")
    def check_num_properties(self):
        if self.num_properties < 1 or self.num_properties > 12:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"num_properties must be 1-12, got {self.num_properties}"
            )
        return self


# ---------------------------------------------------------------------------
# Property slot (output of road generation)
# ---------------------------------------------------------------------------

@dataclass
class PropertySlot:
    """A slot for a property along the road."""

    index: int
    center_x: float  # Center of property in board coordinates
    center_y: float
    road_edge: str  # Which side of the property faces the road
    assigned_preset: str  # Preset name for this property

"""Pydantic models for building parameters, printer profiles, and API responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, field_validator, model_validator


@dataclass
class PrinterProfile:
    """Constraint profile for a specific printer type."""

    # Minimum dimensions (mm)
    min_wall_thickness: float = 0.8
    min_feature_size: float = 0.6
    min_hole_size: float = 0.6
    min_column_diameter: float = 0.8
    min_column_width: float = 0.6
    min_emboss_width: float = 0.5
    min_emboss_height: float = 0.2
    min_engrave_width: float = 0.4
    min_engrave_depth: float = 0.2

    # Structural limits
    max_overhang_angle: float = 45.0
    max_bridge_span: float = 6.0
    max_aspect_ratio: float = 6.0

    # Base
    base_thickness: float = 2.5
    base_chamfer: float = 0.5

    # Cylinders
    cylinder_segments_per_mm: int = 8
    min_cylinder_segments: int = 8
    max_cylinder_segments: int = 48

    # Feature gating
    use_window_frames: bool = True
    use_individual_balusters: bool = False
    use_arched_windows: bool = False
    use_dormers: bool = True

    @classmethod
    def fdm(cls) -> PrinterProfile:
        """FDM printer profile for hotel-scale pieces."""
        return cls()

    @classmethod
    def monopoly_fdm(cls) -> PrinterProfile:
        """Legacy FDM profile for Monopoly-scale pieces."""
        return cls(
            base_thickness=1.2,
            base_chamfer=0.3,
            use_window_frames=False,
            use_dormers=False,
        )

    @classmethod
    def resin(cls) -> PrinterProfile:
        """Resin printer profile for hotel-scale pieces."""
        return cls(
            min_wall_thickness=0.5,
            min_feature_size=0.2,
            min_hole_size=0.3,
            min_column_diameter=0.4,
            min_column_width=0.4,
            min_emboss_width=0.2,
            min_emboss_height=0.1,
            min_engrave_width=0.2,
            min_engrave_depth=0.1,
            max_overhang_angle=55.0,
            max_bridge_span=999.0,
            max_aspect_ratio=10.0,
            base_thickness=2.0,
            base_chamfer=0.3,
            cylinder_segments_per_mm=12,
            min_cylinder_segments=12,
            max_cylinder_segments=64,
            use_window_frames=True,
            use_individual_balusters=True,
            use_arched_windows=True,
            use_dormers=True,
        )

    @classmethod
    def from_type(cls, printer_type: str) -> PrinterProfile:
        """Get profile by printer type string."""
        if printer_type == "fdm":
            return cls.fdm()
        elif printer_type == "resin":
            return cls.resin()
        else:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(f"Unknown printer type: {printer_type}")


class BuildingParams(BaseModel):
    """Parameters for generating a hotel building."""

    style_name: str
    width: float = 30.0
    depth: float = 25.0
    num_floors: int = 7
    floor_height: float = 5.0
    printer_type: str = "fdm"
    seed: int = 42
    max_triangles: int = 100_000
    style_params: dict[str, Any] = {}

    @model_validator(mode="after")
    def check_aspect_ratio(self):
        """Reject extreme aspect ratios."""
        total_height = self.num_floors * self.floor_height
        min_base = min(self.width, self.depth)
        if min_base > 0 and total_height / min_base > 15:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"Aspect ratio {total_height / min_base:.1f}:1 exceeds maximum 15:1"
            )
        return self

    @model_validator(mode="after")
    def check_printer_type(self):
        """Validate printer type."""
        if self.printer_type not in ("fdm", "resin"):
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"printer_type must be 'fdm' or 'resin', got '{self.printer_type}'"
            )
        return self


class BuildingPlacement(BaseModel):
    """Position and size of a single building within a complex."""

    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    width: float = 30.0
    depth: float = 25.0
    num_floors: int = 7
    floor_height: float = 5.0
    role: str = "main"

    @field_validator("role")
    @classmethod
    def check_role(cls, v: str) -> str:
        valid = ("main", "wing", "annex", "tower", "pavilion")
        if v not in valid:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"role must be one of {valid}, got '{v}'"
            )
        return v


class ComplexParams(BaseModel):
    """Parameters for generating a hotel complex (1-6 buildings)."""

    style_name: str
    num_buildings: int = 3
    printer_type: str = "fdm"
    seed: int = 42
    max_triangles: int = 200_000
    style_params: dict[str, Any] = {}
    lot_width: float | None = None
    lot_depth: float | None = None
    building_spacing: float = 5.0
    placements: list[BuildingPlacement] | None = None
    preset: str | None = None

    @model_validator(mode="after")
    def check_num_buildings(self):
        if self.num_buildings < 1 or self.num_buildings > 6:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"num_buildings must be 1-6, got {self.num_buildings}"
            )
        return self

    @model_validator(mode="after")
    def check_spacing(self):
        if self.building_spacing < 2.0:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"building_spacing must be >= 2.0mm, got {self.building_spacing}"
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
    def check_placements_count(self):
        if self.placements is not None and len(self.placements) != self.num_buildings:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"placements has {len(self.placements)} entries but "
                f"num_buildings is {self.num_buildings}"
            )
        return self


class PresetInfo(BaseModel):
    """Preset metadata for API response."""

    name: str
    display_name: str
    description: str
    style_name: str
    num_buildings: int
    building_roles: list[str]


class StyleInfo(BaseModel):
    """Style metadata for API response."""

    name: str
    display_name: str
    description: str
    params_schema: dict[str, Any] = {}


class GenerateResponse(BaseModel):
    """Metadata returned in X-Build-Metadata header."""

    triangle_count: int
    bounding_box: tuple
    is_watertight: bool
    warnings: list[str] = []


class ErrorResponse(BaseModel):
    """Error response body."""

    error_type: str
    message: str
    detail: str | None = None

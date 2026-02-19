"""Pydantic models for building parameters, printer profiles, and API responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, model_validator


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
    base_thickness: float = 1.2
    base_chamfer: float = 0.3

    # Cylinders
    cylinder_segments_per_mm: int = 8
    min_cylinder_segments: int = 8
    max_cylinder_segments: int = 48

    # Feature gating
    use_window_frames: bool = False
    use_individual_balusters: bool = False
    use_arched_windows: bool = False
    use_dormers: bool = False

    @classmethod
    def fdm(cls) -> PrinterProfile:
        """FDM printer profile with conservative constraints."""
        return cls()

    @classmethod
    def resin(cls) -> PrinterProfile:
        """Resin printer profile with fine detail support."""
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
            base_thickness=1.0,
            base_chamfer=0.2,
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
    width: float = 8.0
    depth: float = 6.0
    num_floors: int = 4
    floor_height: float = 0.8
    printer_type: str = "fdm"
    seed: int = 42
    max_triangles: int = 50_000
    style_params: dict[str, Any] = {}

    @model_validator(mode="after")
    def check_aspect_ratio(self):
        """Reject extreme aspect ratios."""
        total_height = self.num_floors * self.floor_height
        min_base = min(self.width, self.depth)
        if min_base > 0 and total_height / min_base > 8:
            from hotel_generator.errors import InvalidParamsError
            raise InvalidParamsError(
                f"Aspect ratio {total_height / min_base:.1f}:1 exceeds maximum 8:1"
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

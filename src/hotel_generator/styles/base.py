"""Abstract style base class, style registry, and shared assembly helper."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from manifold3d import Manifold

from hotel_generator.config import BuildingParams, PrinterProfile
from hotel_generator.errors import GeometryError, InvalidParamsError
from hotel_generator.geometry.booleans import union_all, difference_all


@dataclass(frozen=True)
class GardenTheme:
    """Configuration for a style's garden/leisure area aesthetics."""

    tree_type: str = "deciduous"  # "deciduous", "conifer", "palm"
    tree_density: float = 0.5  # 0.0-1.0, controls Poisson disk spacing
    pool_shape: str | None = "rectangular"  # "rectangular", "kidney", "l_shaped", or None
    pool_size: str = "medium"  # "small", "medium", "large"
    has_hedges: bool = True
    hedge_style: str = "border"  # "border", "formal", "sparse"
    has_terrace: bool = True
    path_style: str = "straight"  # "straight", "curved"


# Global style registry
STYLE_REGISTRY: dict[str, HotelStyle] = {}


def register_style(cls: type[HotelStyle]) -> type[HotelStyle]:
    """Decorator to register a style class in STYLE_REGISTRY."""
    instance = cls()
    STYLE_REGISTRY[instance.name] = instance
    return cls


class HotelStyle(abc.ABC):
    """Abstract base class for architectural styles."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Machine name (e.g., 'modern')."""

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g., 'Modern')."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Short style description."""

    @abc.abstractmethod
    def generate(
        self,
        params: BuildingParams,
        profile: PrinterProfile,
    ) -> Manifold:
        """Generate the building geometry."""

    def style_params_schema(self) -> dict[str, Any]:
        """JSON Schema for style-specific params. Override in subclasses."""
        return {}

    def validate_style_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and clean style-specific params. Override in subclasses."""
        return params

    def preferred_layout_strategy(self) -> str:
        """Return the preferred layout strategy name for this style.

        Override in subclasses. Default is 'row'.
        """
        return "row"

    def garden_theme(self) -> GardenTheme:
        """Return the garden/leisure theme for this style.

        Override in subclasses for style-specific garden aesthetics.
        """
        return GardenTheme()


def list_styles() -> list[dict]:
    """List all registered styles with metadata."""
    return [
        {
            "name": style.name,
            "display_name": style.display_name,
            "description": style.description,
            "params_schema": style.style_params_schema(),
        }
        for style in STYLE_REGISTRY.values()
    ]


def assemble_building(
    shell: Manifold,
    cutouts: list[Manifold] | None = None,
    additions: list[Manifold] | None = None,
    cleanup_cuts: list[Manifold] | None = None,
) -> Manifold:
    """Shared three-phase CSG assembly helper.

    Phase 1: shell - union(cutouts)       (subtract windows, doors)
    Phase 2: + union(additions)           (add roof, columns, balconies)
    Phase 3: - union(cleanup_cuts)        (optional trimming)

    Checks for empty manifold after each phase.
    """
    if shell.is_empty():
        raise GeometryError("Shell manifold is empty before assembly")

    # Phase 1: Subtract cutouts
    result = shell
    if cutouts:
        result = difference_all(result, cutouts)
        if result.is_empty():
            raise GeometryError(
                "Building became empty after subtracting cutouts "
                "(cutouts may be larger than shell)"
            )

    # Phase 2: Add features
    if additions:
        valid_additions = [a for a in additions if not a.is_empty()]
        if valid_additions:
            result = union_all([result] + valid_additions)
            if result.is_empty():
                raise GeometryError("Building became empty after adding features")

    # Phase 3: Cleanup cuts
    if cleanup_cuts:
        result = difference_all(result, cleanup_cuts)
        if result.is_empty():
            raise GeometryError("Building became empty after cleanup cuts")

    return result

"""Scale-aware feature dimensions for architectural components.

ScaleContext computes proportional dimensions from building parameters,
replacing hardcoded absolute values that only worked at Monopoly scale.
Styles construct a ScaleContext at the top of generate() and use its
properties instead of magic numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from hotel_generator.config import PrinterProfile


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value between low and high."""
    return max(low, min(high, value))


@dataclass(frozen=True)
class ScaleContext:
    """Compute scale-appropriate feature dimensions from building params.

    All dimensions scale primarily with floor_height, which is the natural
    "unit of measure" for architectural features.
    """

    width: float
    depth: float
    floor_height: float
    num_floors: int
    profile: PrinterProfile

    # Reference floor height (original Monopoly scale)
    _REF_FLOOR_HEIGHT: ClassVar[float] = 0.8

    @property
    def scale_factor(self) -> float:
        """Overall scale factor relative to Monopoly reference."""
        return self.floor_height / self._REF_FLOOR_HEIGHT

    # --- Window dimensions ---

    @property
    def window_width(self) -> float:
        """Window width, proportional to floor height."""
        return clamp(
            self.floor_height * 0.5,
            self.profile.min_feature_size,
            self.floor_height * 0.7,
        )

    @property
    def window_height(self) -> float:
        """Window height, proportional to floor height."""
        return clamp(
            self.floor_height * 0.65,
            self.profile.min_feature_size,
            self.floor_height * 0.85,
        )

    def windows_per_floor(self, wall_width: float) -> int:
        """Compute appropriate window count for a given wall width."""
        spacing = self.window_width * 2.5  # window + gap on each side
        return max(2, int(wall_width / spacing))

    # --- Door dimensions ---

    @property
    def door_width(self) -> float:
        """Door width, proportional to floor height."""
        return clamp(
            self.floor_height * 1.0,
            self.profile.min_feature_size * 2,
            self.width * 0.2,
        )

    @property
    def door_height(self) -> float:
        """Door height."""
        return self.floor_height * 0.85

    # --- Roof and parapet ---

    @property
    def roof_overhang(self) -> float:
        """Roof overhang beyond walls."""
        return clamp(self.width * 0.03, 0.1, self.width * 0.08)

    @property
    def parapet_height(self) -> float:
        """Parapet wall height above roof."""
        return clamp(self.floor_height * 0.35, 0.15, self.floor_height * 0.6)

    @property
    def parapet_wall_thickness(self) -> float:
        """Thickness of parapet walls."""
        return max(self.profile.min_wall_thickness, self.floor_height * 0.15)

    @property
    def roof_slab_thickness(self) -> float:
        """Thickness of the roof slab."""
        return clamp(self.floor_height * 0.2, 0.1, self.floor_height * 0.4)

    # --- Structural elements ---

    @property
    def column_width(self) -> float:
        """Column diameter/width."""
        return max(self.profile.min_column_width, self.floor_height * 0.3)

    @property
    def wall_thickness(self) -> float:
        """Standard wall thickness."""
        return max(self.profile.min_wall_thickness, self.floor_height * 0.15)

    # --- Decorative elements ---

    @property
    def cornice_height(self) -> float:
        """Cornice/entablature detail height."""
        return clamp(
            self.floor_height * 0.15,
            self.profile.min_emboss_height,
            self.floor_height * 0.3,
        )

    @property
    def entablature_height(self) -> float:
        """Classical entablature height."""
        return self.floor_height * 0.3

    @property
    def fin_thickness(self) -> float:
        """Vertical fin thickness (Art Deco)."""
        return max(self.profile.min_feature_size, self.floor_height * 0.15)

    @property
    def fin_depth(self) -> float:
        """Vertical fin depth/projection."""
        return clamp(self.floor_height * 0.1, 0.1, self.floor_height * 0.2)

    @property
    def setback(self) -> float:
        """Art Deco ziggurat setback per tier."""
        return clamp(self.width * 0.08, 0.3, self.width * 0.12)

    # --- Protrusions ---

    @property
    def bay_depth(self) -> float:
        """Bay window projection depth."""
        return clamp(self.depth * 0.08, 0.3, self.depth * 0.15)

    @property
    def stoop_step_height(self) -> float:
        """Height of a single stoop step."""
        return clamp(self.floor_height * 0.08, 0.2, self.floor_height * 0.15)

    @property
    def stoop_step_depth(self) -> float:
        """Depth of a single stoop step."""
        return clamp(self.floor_height * 0.1, 0.2, self.floor_height * 0.2)

    @property
    def eave_overhang(self) -> float:
        """Eave/roof overhang for Mediterranean/Tropical styles."""
        return clamp(self.width * 0.06, 0.3, self.width * 0.12)

    @property
    def loggia_depth(self) -> float:
        """Loggia/colonnade depth."""
        return clamp(self.depth * 0.06, 0.2, self.depth * 0.12)

    @property
    def mansard_inset(self) -> float:
        """Mansard roof inset from walls."""
        return clamp(self.width * 0.08, 0.3, self.width * 0.15)

    # --- Turret (Victorian) ---

    @property
    def turret_radius(self) -> float:
        """Victorian turret radius."""
        return max(
            self.profile.min_column_diameter,
            self.width * 0.12,
        )

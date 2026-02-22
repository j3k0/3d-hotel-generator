"""Garden layout engine: places landscape features on a property plate.

Given a lot rectangle, building footprints, road edge, and a GardenTheme,
this engine determines where to place trees, pools, hedges, paths, and
terraces. Tree placement uses Poisson disk sampling for natural spacing.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from hotel_generator.board.config import GardenFeaturePlacement
from hotel_generator.config import BuildingPlacement
from hotel_generator.styles.base import GardenTheme


# ---------------------------------------------------------------------------
# Pool size presets (width, depth in mm)
# ---------------------------------------------------------------------------

POOL_SIZES = {
    "small": (12.0, 8.0),
    "medium": (18.0, 11.0),
    "large": (25.0, 15.0),
}

# ---------------------------------------------------------------------------
# Building footprint helpers
# ---------------------------------------------------------------------------

@dataclass
class Rect:
    """Axis-aligned rectangle."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def cx(self) -> float:
        return (self.min_x + self.max_x) / 2

    @property
    def cy(self) -> float:
        return (self.min_y + self.max_y) / 2

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (
            self.min_x - margin <= x <= self.max_x + margin
            and self.min_y - margin <= y <= self.max_y + margin
        )


def _building_footprint(p: BuildingPlacement) -> Rect:
    """Get the axis-aligned bounding rect of a building placement."""
    if p.rotation in (90, 270, -90, -270):
        hw, hd = p.depth / 2, p.width / 2
    else:
        hw, hd = p.width / 2, p.depth / 2
    return Rect(p.x - hw, p.y - hd, p.x + hw, p.y + hd)


# ---------------------------------------------------------------------------
# Main layout engine
# ---------------------------------------------------------------------------

class GardenLayoutEngine:
    """Computes positions for garden features within a property lot."""

    def compute_layout(
        self,
        lot_width: float,
        lot_depth: float,
        road_edge: str,
        road_width: float,
        building_placements: list[BuildingPlacement],
        garden_theme: GardenTheme,
        rng: random.Random,
    ) -> list[GardenFeaturePlacement]:
        """Compute garden element placements.

        Coordinate system:
        - Lot centered on X, extends from y=0 to y=lot_depth
        - Road strip occupies the ``road_edge`` side
        - Buildings are positioned in the building zone (center of lot)
        - Garden fills remaining space

        For simplicity, we always work in the canonical orientation
        (road on south / y=0 side) and the caller rotates as needed.

        Returns:
            List of GardenFeaturePlacement objects.
        """
        features: list[GardenFeaturePlacement] = []

        # Building footprints as exclusion rects
        bldg_rects = [_building_footprint(p) for p in building_placements]
        bldg_margin = 3.0  # mm clearance around buildings

        # Find the main building (first one or the "main" role)
        main_bldg = building_placements[0] if building_placements else None
        for p in building_placements:
            if p.role == "main":
                main_bldg = p
                break

        # Garden zone boundaries (road strip removed)
        garden_y_min = road_width + 1.0  # slight margin from road
        garden_y_max = lot_depth - 1.0
        garden_x_min = -lot_width / 2 + 1.0
        garden_x_max = lot_width / 2 - 1.0

        # --- Terrace (entrance plaza near main building, between building and road) ---
        if garden_theme.has_terrace and main_bldg is not None:
            main_rect = _building_footprint(main_bldg)
            terrace_w = min(main_rect.max_x - main_rect.min_x + 4.0, lot_width * 0.3)
            terrace_d = max(3.0, (main_rect.min_y - garden_y_min) * 0.4)
            terrace_y = main_rect.min_y - terrace_d / 2 - 0.5
            if terrace_y > garden_y_min + 1.0:
                features.append(GardenFeaturePlacement(
                    feature_type="terrace",
                    x=main_rect.cx,
                    y=terrace_y,
                    params={"width": terrace_w, "depth": terrace_d, "height": 0.5},
                ))

        # --- Pool ---
        if garden_theme.pool_shape is not None:
            pool_w, pool_d = POOL_SIZES.get(garden_theme.pool_size, POOL_SIZES["medium"])
            pool_pos = self._find_pool_position(
                pool_w, pool_d, bldg_rects, bldg_margin,
                garden_x_min, garden_x_max, garden_y_min, garden_y_max,
                main_bldg, rng,
            )
            if pool_pos is not None:
                px, py = pool_pos
                features.append(GardenFeaturePlacement(
                    feature_type="pool",
                    x=px,
                    y=py,
                    params={
                        "width": pool_w,
                        "depth": pool_d,
                        "shape": garden_theme.pool_shape,
                    },
                ))

        # --- Main path (road to main building entrance) ---
        if main_bldg is not None:
            main_rect = _building_footprint(main_bldg)
            path_points = self._compute_path_points(
                main_rect, road_width, garden_theme.path_style, rng,
            )
            if path_points:
                features.append(GardenFeaturePlacement(
                    feature_type="path",
                    x=0, y=0,
                    params={"points": path_points, "width": 2.0, "height": 0.3},
                ))

        # --- Hedges ---
        if garden_theme.has_hedges:
            hedge_features = self._place_hedges(
                garden_theme.hedge_style,
                lot_width, lot_depth, road_width,
                bldg_rects, bldg_margin, rng,
            )
            features.extend(hedge_features)

        # --- Trees (Poisson disk sampling) ---
        tree_features = self._place_trees(
            garden_theme.tree_type,
            garden_theme.tree_density,
            lot_width, lot_depth, road_width,
            bldg_rects, bldg_margin,
            features,  # existing features as additional exclusion
            rng,
        )
        features.extend(tree_features)

        return features

    # ------------------------------------------------------------------
    # Pool placement
    # ------------------------------------------------------------------

    def _find_pool_position(
        self,
        pool_w: float,
        pool_d: float,
        bldg_rects: list[Rect],
        bldg_margin: float,
        x_min: float, x_max: float,
        y_min: float, y_max: float,
        main_bldg: BuildingPlacement | None,
        rng: random.Random,
    ) -> tuple[float, float] | None:
        """Find a suitable position for the pool, behind/beside the main building."""
        if main_bldg is None:
            # Center of garden zone
            cx = (x_min + x_max) / 2
            cy = (y_min + y_max) / 2
            return (cx, cy)

        main_rect = _building_footprint(main_bldg)

        # Try behind main building first (higher Y)
        candidates = [
            (main_rect.cx, main_rect.max_y + bldg_margin + pool_d / 2),
            (main_rect.cx + main_rect.max_x - main_rect.min_x, main_rect.cy),
            (main_rect.cx - main_rect.max_x + main_rect.min_x, main_rect.cy),
        ]

        for cx, cy in candidates:
            pool_rect = Rect(cx - pool_w / 2, cy - pool_d / 2,
                             cx + pool_w / 2, cy + pool_d / 2)
            # Check within garden bounds
            if (pool_rect.min_x < x_min or pool_rect.max_x > x_max
                    or pool_rect.min_y < y_min or pool_rect.max_y > y_max):
                continue
            # Check no overlap with buildings
            if any(self._rects_overlap(pool_rect, br, bldg_margin) for br in bldg_rects):
                continue
            return (cx, cy)

        return None

    # ------------------------------------------------------------------
    # Path computation
    # ------------------------------------------------------------------

    def _compute_path_points(
        self,
        main_rect: Rect,
        road_width: float,
        path_style: str,
        rng: random.Random,
    ) -> list[list[float]]:
        """Compute path waypoints from road edge to main building entrance."""
        start_x = main_rect.cx
        start_y = road_width * 0.5  # middle of road strip
        end_y = main_rect.min_y - 0.5

        if end_y <= start_y + 1.0:
            return []

        if path_style == "curved":
            # S-curve: add a midpoint offset
            mid_y = (start_y + end_y) / 2
            offset = rng.uniform(-3.0, 3.0)
            return [
                [start_x, start_y],
                [start_x + offset, mid_y],
                [start_x, end_y],
            ]
        else:
            # Straight path
            return [
                [start_x, start_y],
                [start_x, end_y],
            ]

    # ------------------------------------------------------------------
    # Hedge placement
    # ------------------------------------------------------------------

    def _place_hedges(
        self,
        hedge_style: str,
        lot_width: float, lot_depth: float,
        road_width: float,
        bldg_rects: list[Rect],
        bldg_margin: float,
        rng: random.Random,
    ) -> list[GardenFeaturePlacement]:
        """Place hedges based on style."""
        features: list[GardenFeaturePlacement] = []
        hedge_h = 1.5
        hedge_w = 1.0
        margin = 1.5

        if hedge_style in ("border", "formal"):
            # Left border hedge
            length = lot_depth - road_width - 2 * margin
            if length > 5.0:
                features.append(GardenFeaturePlacement(
                    feature_type="hedge",
                    x=-lot_width / 2 + margin,
                    y=road_width + margin + length / 2,
                    rotation=90.0,
                    params={"length": length, "height": hedge_h, "width": hedge_w},
                ))
                # Right border hedge
                features.append(GardenFeaturePlacement(
                    feature_type="hedge",
                    x=lot_width / 2 - margin,
                    y=road_width + margin + length / 2,
                    rotation=90.0,
                    params={"length": length, "height": hedge_h, "width": hedge_w},
                ))

        if hedge_style == "formal":
            # Additional cross hedges for formal gardens
            cross_y = lot_depth * 0.7
            cross_length = lot_width * 0.3
            for side in (-1, 1):
                cx = side * lot_width * 0.25
                # Check no overlap with buildings
                hedge_rect = Rect(cx - cross_length / 2, cross_y - hedge_w / 2,
                                  cx + cross_length / 2, cross_y + hedge_w / 2)
                if not any(self._rects_overlap(hedge_rect, br, bldg_margin) for br in bldg_rects):
                    features.append(GardenFeaturePlacement(
                        feature_type="hedge",
                        x=cx,
                        y=cross_y,
                        params={"length": cross_length, "height": hedge_h, "width": hedge_w},
                    ))

        return features

    # ------------------------------------------------------------------
    # Tree placement (Poisson disk sampling)
    # ------------------------------------------------------------------

    def _place_trees(
        self,
        tree_type: str,
        tree_density: float,
        lot_width: float, lot_depth: float,
        road_width: float,
        bldg_rects: list[Rect],
        bldg_margin: float,
        existing_features: list[GardenFeaturePlacement],
        rng: random.Random,
    ) -> list[GardenFeaturePlacement]:
        """Place trees using Poisson disk dart-throwing."""
        if tree_density <= 0.01:
            return []

        # Spacing inversely proportional to density
        min_spacing = max(4.0, 12.0 * (1.0 - tree_density))
        max_trees = max(2, int(tree_density * 20))

        # Exclusion zones: buildings + pools + terraces
        exclusion_rects = list(bldg_rects)
        for f in existing_features:
            if f.feature_type == "pool":
                pw = f.params.get("width", 18.0)
                pd = f.params.get("depth", 11.0)
                exclusion_rects.append(Rect(
                    f.x - pw / 2 - 2.0, f.y - pd / 2 - 2.0,
                    f.x + pw / 2 + 2.0, f.y + pd / 2 + 2.0,
                ))
            elif f.feature_type == "terrace":
                tw = f.params.get("width", 10.0)
                td = f.params.get("depth", 5.0)
                exclusion_rects.append(Rect(
                    f.x - tw / 2 - 1.0, f.y - td / 2 - 1.0,
                    f.x + tw / 2 + 1.0, f.y + td / 2 + 1.0,
                ))

        # Garden bounds (excluding road strip)
        x_min = -lot_width / 2 + 2.0
        x_max = lot_width / 2 - 2.0
        y_min = road_width + 2.0
        y_max = lot_depth - 2.0

        if x_max <= x_min or y_max <= y_min:
            return []

        placed: list[tuple[float, float]] = []
        features: list[GardenFeaturePlacement] = []
        max_attempts = 30

        for _ in range(max_trees):
            for _ in range(max_attempts):
                tx = rng.uniform(x_min, x_max)
                ty = rng.uniform(y_min, y_max)

                # Check min spacing from other trees
                too_close = False
                for px, py in placed:
                    if math.sqrt((tx - px) ** 2 + (ty - py) ** 2) < min_spacing:
                        too_close = True
                        break
                if too_close:
                    continue

                # Check not inside exclusion zones
                in_exclusion = False
                for rect in exclusion_rects:
                    if rect.contains(tx, ty, margin=bldg_margin):
                        in_exclusion = True
                        break
                if in_exclusion:
                    continue

                # Valid position found
                placed.append((tx, ty))
                tree_height = rng.uniform(3.5, 5.5)
                features.append(GardenFeaturePlacement(
                    feature_type=f"{tree_type}_tree",
                    x=tx,
                    y=ty,
                    params={"height": tree_height},
                ))
                break

        return features

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rects_overlap(a: Rect, b: Rect, margin: float = 0.0) -> bool:
        """Check if two axis-aligned rects overlap (with margin)."""
        return not (
            a.max_x + margin <= b.min_x
            or b.max_x + margin <= a.min_x
            or a.max_y + margin <= b.min_y
            or b.max_y + margin <= a.min_y
        )

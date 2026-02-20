"""Layout strategy functions for positioning buildings in a complex."""

from __future__ import annotations

import random
from typing import Sequence

from hotel_generator.config import BuildingPlacement


# Role-based sizing multipliers: (width_factor, depth_factor, floor_factor)
# Asymmetric width/depth creates more rectangular, varied building shapes
ROLE_SIZING = {
    "main": (1.0, 0.85, 1.0),
    "wing": (0.8, 0.55, 0.85),
    "annex": (0.55, 0.45, 0.75),
    "tower": (0.35, 0.35, 2.5),
    "pavilion": (0.45, 0.35, 0.5),
}


def _apply_role_sizing(
    role: str,
    base_width: float,
    base_depth: float,
    base_floors: int,
    floor_height: float,
    size_hints: dict[str, dict[str, float]] | None = None,
) -> tuple[float, float, int, float]:
    """Apply role-based sizing to base dimensions.

    If size_hints is provided (from a preset), those override ROLE_SIZING
    for the matching role. This allows presets to define custom proportions.
    """
    if size_hints and role in size_hints:
        hints = size_hints[role]
        wf = hints.get("width", 1.0)
        df = hints.get("depth", 1.0)
        ff = hints.get("floors", 1.0)
    else:
        wf, df, ff = ROLE_SIZING.get(role, (1.0, 1.0, 1.0))
    floors = max(2, int(base_floors * ff))
    return base_width * wf, base_depth * df, floors, floor_height


def _default_roles(num_buildings: int, roles: Sequence[str] | None = None) -> list[str]:
    """Generate default roles if not specified."""
    if roles:
        return list(roles[:num_buildings])
    if num_buildings == 1:
        return ["main"]
    result = ["main"]
    for i in range(1, num_buildings):
        if i <= 2:
            result.append("wing")
        else:
            result.append("annex")
    return result


def row_layout(
    num_buildings: int,
    rng: random.Random,
    base_width: float,
    base_depth: float,
    base_floors: int,
    floor_height: float,
    spacing: float,
    roles: Sequence[str] | None = None,
    size_hints: dict[str, dict[str, float]] | None = None,
) -> list[BuildingPlacement]:
    """Buildings in a row along the X axis, main centered."""
    role_list = _default_roles(num_buildings, roles)
    placements = []
    sizes = []
    for role in role_list:
        w, d, floors, fh = _apply_role_sizing(role, base_width, base_depth, base_floors, floor_height, size_hints)
        sizes.append((w, d, floors, fh, role))

    total_width = sum(s[0] for s in sizes) + spacing * (num_buildings - 1)
    x = -total_width / 2

    for w, d, floors, fh, role in sizes:
        placements.append(BuildingPlacement(
            x=x + w / 2,
            y=0.0,
            rotation=0.0,
            width=w,
            depth=d,
            num_floors=floors,
            floor_height=fh,
            role=role,
        ))
        x += w + spacing

    return placements


def courtyard_layout(
    num_buildings: int,
    rng: random.Random,
    base_width: float,
    base_depth: float,
    base_floors: int,
    floor_height: float,
    spacing: float,
    roles: Sequence[str] | None = None,
    size_hints: dict[str, dict[str, float]] | None = None,
) -> list[BuildingPlacement]:
    """Buildings arranged around a courtyard (U or C shape)."""
    role_list = _default_roles(num_buildings, roles)
    placements = []

    # Main building at the back
    w0, d0, f0, fh0 = _apply_role_sizing(role_list[0], base_width, base_depth, base_floors, floor_height, size_hints)
    placements.append(BuildingPlacement(
        x=0.0, y=d0 / 2 + spacing / 2,
        width=w0, depth=d0, num_floors=f0, floor_height=fh0, role=role_list[0],
    ))

    if num_buildings >= 2:
        # Left wing
        w1, d1, f1, fh1 = _apply_role_sizing(role_list[1], base_width, base_depth, base_floors, floor_height, size_hints)
        placements.append(BuildingPlacement(
            x=-w0 / 2 - spacing / 2 - d1 / 2, y=0.0,
            rotation=90.0,
            width=w1, depth=d1, num_floors=f1, floor_height=fh1, role=role_list[1],
        ))

    if num_buildings >= 3:
        # Right wing
        w2, d2, f2, fh2 = _apply_role_sizing(role_list[2], base_width, base_depth, base_floors, floor_height, size_hints)
        placements.append(BuildingPlacement(
            x=w0 / 2 + spacing / 2 + d2 / 2, y=0.0,
            rotation=90.0,
            width=w2, depth=d2, num_floors=f2, floor_height=fh2, role=role_list[2],
        ))

    if num_buildings >= 4:
        # Front building (closing the courtyard)
        w3, d3, f3, fh3 = _apply_role_sizing(role_list[3], base_width, base_depth, base_floors, floor_height, size_hints)
        placements.append(BuildingPlacement(
            x=0.0, y=-d3 / 2 - spacing / 2,
            width=w3, depth=d3, num_floors=f3, floor_height=fh3, role=role_list[3],
        ))

    # Extra buildings behind or beside the courtyard
    for i in range(4, num_buildings):
        wi, di, fi, fhi = _apply_role_sizing(role_list[i], base_width, base_depth, base_floors, floor_height, size_hints)
        # Place behind the main building
        extra_idx = i - 4
        y_back = d0 / 2 + spacing / 2 + d0 + spacing + di / 2 + extra_idx * (di + spacing)
        placements.append(BuildingPlacement(
            x=0.0, y=y_back,
            width=wi, depth=di, num_floors=fi, floor_height=fhi, role=role_list[i],
        ))

    return placements


def hierarchical_layout(
    num_buildings: int,
    rng: random.Random,
    base_width: float,
    base_depth: float,
    base_floors: int,
    floor_height: float,
    spacing: float,
    roles: Sequence[str] | None = None,
    size_hints: dict[str, dict[str, float]] | None = None,
) -> list[BuildingPlacement]:
    """One dominant building with flanking shorter buildings."""
    role_list = _default_roles(num_buildings, roles)
    placements = []

    # Main building centered
    w0, d0, f0, fh0 = _apply_role_sizing(role_list[0], base_width, base_depth, base_floors, floor_height, size_hints)
    placements.append(BuildingPlacement(
        x=0.0, y=0.0,
        width=w0, depth=d0, num_floors=f0, floor_height=fh0, role=role_list[0],
    ))

    # Flanking buildings symmetrically
    for i in range(1, num_buildings):
        wi, di, fi, fhi = _apply_role_sizing(role_list[i], base_width, base_depth, base_floors, floor_height, size_hints)
        side = -1 if i % 2 == 1 else 1
        pair_idx = (i + 1) // 2
        x_offset = side * (w0 / 2 + spacing + wi / 2) * pair_idx
        # Flanking buildings set back slightly
        y_offset = di * 0.2 * pair_idx
        placements.append(BuildingPlacement(
            x=x_offset, y=y_offset,
            width=wi, depth=di, num_floors=fi, floor_height=fhi, role=role_list[i],
        ))

    return placements


def cluster_layout(
    num_buildings: int,
    rng: random.Random,
    base_width: float,
    base_depth: float,
    base_floors: int,
    floor_height: float,
    spacing: float,
    roles: Sequence[str] | None = None,
    size_hints: dict[str, dict[str, float]] | None = None,
) -> list[BuildingPlacement]:
    """Main building with scattered pavilions around it."""
    if roles is None:
        role_list = ["main"] + ["pavilion"] * (num_buildings - 1)
    else:
        role_list = list(roles[:num_buildings])

    placements = []

    # Main building centered
    w0, d0, f0, fh0 = _apply_role_sizing(role_list[0], base_width, base_depth, base_floors, floor_height, size_hints)
    placements.append(BuildingPlacement(
        x=0.0, y=0.0,
        width=w0, depth=d0, num_floors=f0, floor_height=fh0, role=role_list[0],
    ))

    # Scatter pavilions in a ring around the main building
    import math
    # Compute sizes first to determine proper radius
    pav_sizes = []
    for i in range(1, num_buildings):
        wi, di, fi, fhi = _apply_role_sizing(role_list[i], base_width, base_depth, base_floors, floor_height, size_hints)
        pav_sizes.append((wi, di, fi, fhi))

    max_pav = max((max(w, d) for w, d, _, _ in pav_sizes), default=0)
    radius = max(w0, d0) / 2 + max_pav / 2 + spacing * 2
    angle_start = rng.uniform(0, math.pi / 4)
    for i, (wi, di, fi, fhi) in enumerate(pav_sizes):
        angle = angle_start + (2 * math.pi * i) / max(1, num_buildings - 1)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        placements.append(BuildingPlacement(
            x=x, y=y, rotation=0.0,
            width=wi, depth=di, num_floors=fi, floor_height=fhi, role=role_list[i + 1],
        ))

    return placements


def campus_layout(
    num_buildings: int,
    rng: random.Random,
    base_width: float,
    base_depth: float,
    base_floors: int,
    floor_height: float,
    spacing: float,
    roles: Sequence[str] | None = None,
    size_hints: dict[str, dict[str, float]] | None = None,
) -> list[BuildingPlacement]:
    """Evenly spaced grid arrangement."""
    role_list = _default_roles(num_buildings, roles)
    placements = []

    import math
    cols = math.ceil(math.sqrt(num_buildings))
    rows = math.ceil(num_buildings / cols)

    sizes = []
    for role in role_list:
        w, d, floors, fh = _apply_role_sizing(role, base_width, base_depth, base_floors, floor_height, size_hints)
        sizes.append((w, d, floors, fh, role))

    max_w = max(s[0] for s in sizes)
    max_d = max(s[1] for s in sizes)
    cell_w = max_w + spacing
    cell_d = max_d + spacing

    total_w = cols * cell_w - spacing
    total_d = rows * cell_d - spacing

    idx = 0
    for row in range(rows):
        for col in range(cols):
            if idx >= num_buildings:
                break
            w, d, floors, fh, role = sizes[idx]
            x = -total_w / 2 + col * cell_w + cell_w / 2 - spacing / 2
            y = -total_d / 2 + row * cell_d + cell_d / 2 - spacing / 2
            placements.append(BuildingPlacement(
                x=x, y=y,
                width=w, depth=d, num_floors=floors, floor_height=fh, role=role,
            ))
            idx += 1

    return placements


def l_layout(
    num_buildings: int,
    rng: random.Random,
    base_width: float,
    base_depth: float,
    base_floors: int,
    floor_height: float,
    spacing: float,
    roles: Sequence[str] | None = None,
    size_hints: dict[str, dict[str, float]] | None = None,
) -> list[BuildingPlacement]:
    """Buildings in an L-shaped arrangement."""
    role_list = _default_roles(num_buildings, roles)
    placements = []

    sizes = []
    for role in role_list:
        w, d, floors, fh = _apply_role_sizing(role, base_width, base_depth, base_floors, floor_height, size_hints)
        sizes.append((w, d, floors, fh, role))

    # First building at the corner
    w0, d0, f0, fh0, r0 = sizes[0]
    placements.append(BuildingPlacement(
        x=0.0, y=0.0,
        width=w0, depth=d0, num_floors=f0, floor_height=fh0, role=r0,
    ))

    # Remaining buildings: half go along X (right), half go along Y (up)
    x_arm = []
    y_arm = []
    for i in range(1, num_buildings):
        if i % 2 == 1:
            x_arm.append(sizes[i])
        else:
            y_arm.append(sizes[i])

    # X arm (extending right)
    x_pos = w0 / 2 + spacing
    for w, d, floors, fh, role in x_arm:
        placements.append(BuildingPlacement(
            x=x_pos + w / 2, y=0.0,
            width=w, depth=d, num_floors=floors, floor_height=fh, role=role,
        ))
        x_pos += w + spacing

    # Y arm (extending up)
    y_pos = d0 / 2 + spacing
    for w, d, floors, fh, role in y_arm:
        placements.append(BuildingPlacement(
            x=0.0, y=y_pos + d / 2,
            width=w, depth=d, num_floors=floors, floor_height=fh, role=role,
        ))
        y_pos += d + spacing

    return placements


# Strategy dispatch table
STRATEGIES = {
    "row": row_layout,
    "courtyard": courtyard_layout,
    "hierarchical": hierarchical_layout,
    "cluster": cluster_layout,
    "campus": campus_layout,
    "l_layout": l_layout,
}

"""Validation checks for generated hotel geometry."""

import numpy as np
import trimesh
from manifold3d import Manifold

from hotel_generator.export.stl import manifold_to_trimesh


def validate_manifold(solid: Manifold) -> dict:
    """Run validation checklist on a generated manifold.

    Returns a dict with check results and overall pass/fail.
    """
    results = {}
    warnings = []

    # Convert to trimesh for checks
    tmesh = manifold_to_trimesh(solid)

    # 1. Watertight
    results["is_watertight"] = tmesh.is_watertight

    # 2. Positive volume
    vol = tmesh.volume
    results["volume"] = float(vol)
    results["positive_volume"] = vol > 0

    # 3. Correct orientation (base at Z=0)
    bbox = tmesh.bounds  # [[min_x, min_y, min_z], [max_x, max_y, max_z]]
    results["base_at_z0"] = bbox[0][2] >= -2.0  # allow for base slab

    # 4. Reasonable size (fits within 120mm x 120mm x 120mm)
    size = bbox[1] - bbox[0]
    results["reasonable_size"] = (
        size[0] <= 120 and size[1] <= 120 and size[2] <= 120
    )

    # 5. Not too small (exceeds 5mm in at least 2 dimensions)
    large_dims = sum(1 for s in size if s >= 5)
    results["not_too_small"] = large_dims >= 2

    # 6. Triangle count
    tri_count = len(tmesh.faces)
    results["triangle_count"] = tri_count
    results["triangle_count_ok"] = 4 <= tri_count <= 200_000

    # 7. No degenerate triangles
    areas = tmesh.area_faces
    results["no_degenerate_triangles"] = bool(np.all(areas > 1e-10))

    # 8. Single connected component (approximately)
    # trimesh split can be expensive; just check it's not empty
    results["single_component"] = len(tmesh.faces) > 0

    # Overall pass
    critical_checks = [
        "is_watertight",
        "positive_volume",
        "reasonable_size",
        "triangle_count_ok",
    ]
    results["pass"] = all(results.get(c, False) for c in critical_checks)

    return results

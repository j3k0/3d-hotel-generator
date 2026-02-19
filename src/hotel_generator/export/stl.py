"""STL export via trimesh with shared vertices for watertight output."""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold


def manifold_to_trimesh(solid: Manifold) -> trimesh.Trimesh:
    """Convert a Manifold to a trimesh.Trimesh with shared vertices.

    Uses vert_properties[:, :3] for vertices and tri_verts for faces.
    """
    mesh = solid.to_mesh()
    vertices = np.array(mesh.vert_properties[:, :3], dtype=np.float64)
    faces = np.array(mesh.tri_verts, dtype=np.int32)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def export_stl_bytes(solid: Manifold) -> bytes:
    """Export a Manifold as binary STL bytes."""
    tmesh = manifold_to_trimesh(solid)
    buffer = io.BytesIO()
    tmesh.export(buffer, file_type="stl")
    return buffer.getvalue()


def export_complex_to_directory(
    result: "ComplexResult",  # noqa: F821
    output_dir: str | Path,
) -> list[str]:
    """Export a hotel complex as separate STL files to a directory.

    Creates:
    - base_plate.stl
    - building_01_<role>.stl, building_02_<role>.stl, ...
    - manifest.json with metadata

    Args:
        result: ComplexResult from ComplexBuilder.build()
        output_dir: Directory to write files to (created if needed).

    Returns:
        List of created file paths (relative to output_dir).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    created: list[str] = []

    # Base plate
    base_path = "base_plate.stl"
    stl_bytes = export_stl_bytes(result.base_plate)
    (out / base_path).write_bytes(stl_bytes)
    created.append(base_path)

    # Individual buildings
    for i, (building, placement) in enumerate(
        zip(result.buildings, result.placements)
    ):
        role = placement.role
        filename = f"building_{i + 1:02d}_{role}.stl"
        stl_bytes = export_stl_bytes(building.manifold)
        (out / filename).write_bytes(stl_bytes)
        created.append(filename)

    # Manifest
    manifest = {
        "num_buildings": len(result.buildings),
        "lot_width": result.lot_width,
        "lot_depth": result.lot_depth,
        "files": created,
        "placements": [
            {
                "x": p.x,
                "y": p.y,
                "rotation": p.rotation,
                "width": p.width,
                "depth": p.depth,
                "num_floors": p.num_floors,
                "floor_height": p.floor_height,
                "role": p.role,
            }
            for p in result.placements
        ],
        **result.metadata,
    }
    manifest_path = "manifest.json"
    (out / manifest_path).write_text(json.dumps(manifest, indent=2))
    created.append(manifest_path)

    return created

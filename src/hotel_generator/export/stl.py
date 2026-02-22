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


def export_property_to_directory(
    result: "PropertyResult",  # noqa: F821
    output_dir: str | Path,
) -> list[str]:
    """Export a property plate as separate STL files to a directory.

    Creates:
    - property_plate.stl (combined plate with base, road, gardens)
    - building_01_<role>.stl, building_02_<role>.stl, ...
    - manifest.json with metadata

    Args:
        result: PropertyResult from PropertyBuilder.build()
        output_dir: Directory to write files to (created if needed).

    Returns:
        List of created file paths (relative to output_dir).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    created: list[str] = []

    # Combined property plate
    plate_path = "property_plate.stl"
    stl_bytes = export_stl_bytes(result.plate)
    (out / plate_path).write_bytes(stl_bytes)
    created.append(plate_path)

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
        "num_garden_features": len(result.garden_placements),
        "files": created,
        "placements": [
            {
                "x": p.x, "y": p.y, "rotation": p.rotation,
                "width": p.width, "depth": p.depth,
                "num_floors": p.num_floors, "floor_height": p.floor_height,
                "role": p.role,
            }
            for p in result.placements
        ],
        "garden_features": [
            {
                "type": gf.feature_type,
                "x": gf.x, "y": gf.y,
                "rotation": gf.rotation,
            }
            for gf in result.garden_placements
        ],
        **result.metadata,
    }
    manifest_path = "manifest.json"
    (out / manifest_path).write_text(json.dumps(manifest, indent=2))
    created.append(manifest_path)

    return created


def export_board_to_directory(
    result: "BoardResult",  # noqa: F821
    output_dir: str | Path,
) -> list[str]:
    """Export a full game board as separate property directories.

    Creates:
    - property_01_<preset>/property_plate.stl + buildings + manifest.json
    - property_02_<preset>/...
    - board_manifest.json with overall layout

    Args:
        result: BoardResult from BoardBuilder.build()
        output_dir: Root directory to write files to.

    Returns:
        List of all created file paths (relative to output_dir).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_created: list[str] = []

    for i, (prop, slot) in enumerate(
        zip(result.properties, result.property_slots)
    ):
        preset = slot.assigned_preset
        prop_dir = f"property_{i + 1:02d}_{preset}"
        files = export_property_to_directory(prop, out / prop_dir)
        all_created.extend(f"{prop_dir}/{f}" for f in files)

    # Export frame pieces (if present)
    if result.frame and result.frame.all_pieces:
        frame_dir = out / "frame"
        frame_dir.mkdir(parents=True, exist_ok=True)
        frame_files: list[str] = []
        for piece in result.frame.all_pieces:
            filename = f"{piece.label}.stl"
            stl_bytes = export_stl_bytes(piece.manifold)
            (frame_dir / filename).write_bytes(stl_bytes)
            frame_files.append(filename)
            all_created.append(f"frame/{filename}")

        frame_manifest = {
            "num_pieces": len(result.frame.all_pieces),
            "road_fillers": len(result.frame.road_fillers),
            "road_sides": len(result.frame.road_sides),
            "road_corners": len(result.frame.road_corners),
            "frame_rails": len(result.frame.frame_rails),
            "files": frame_files,
            "pieces": [
                {
                    "label": p.label,
                    "type": p.piece_type,
                    "x": p.x,
                    "y": p.y,
                    "rotation": p.rotation,
                }
                for p in result.frame.all_pieces
            ],
        }
        frame_manifest_path = "frame/frame_manifest.json"
        (frame_dir / "frame_manifest.json").write_text(
            json.dumps(frame_manifest, indent=2)
        )
        all_created.append(frame_manifest_path)

    # Board-level manifest
    board_manifest = {
        "num_properties": len(result.properties),
        "road_shape": result.road_shape,
        "has_frame": result.frame is not None and len(result.frame.all_pieces) > 0,
        "property_slots": [
            {
                "index": s.index,
                "center_x": s.center_x,
                "center_y": s.center_y,
                "road_edge": s.road_edge,
                "preset": s.assigned_preset,
            }
            for s in result.property_slots
        ],
        **result.metadata,
    }
    manifest_path = "board_manifest.json"
    (out / manifest_path).write_text(json.dumps(board_manifest, indent=2))
    all_created.append(manifest_path)

    return all_created


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

"""GLB export via trimesh with vertex normals for web preview."""

import io

import numpy as np
import trimesh
from manifold3d import Manifold


def manifold_to_trimesh_glb(
    solid: Manifold, sharp_angle: float = 50.0
) -> trimesh.Trimesh:
    """Convert a Manifold to a trimesh.Trimesh with split normals for rendering.

    For GLB/web preview, vertices are split at sharp edges to give
    proper per-face-vertex normals. This is expected for rendering
    but not suitable for watertightness checks.
    """
    mesh = solid.to_mesh()
    vertices = np.array(mesh.vert_properties[:, :3], dtype=np.float64)
    faces = np.array(mesh.tri_verts, dtype=np.int32)
    tmesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return tmesh


def export_glb_bytes(solid: Manifold) -> bytes:
    """Export a Manifold as GLB bytes for web preview."""
    tmesh = manifold_to_trimesh_glb(solid)
    # Export as GLB (binary glTF)
    scene = trimesh.Scene(geometry={"hotel": tmesh})
    buffer = io.BytesIO()
    scene.export(buffer, file_type="glb")
    return buffer.getvalue()

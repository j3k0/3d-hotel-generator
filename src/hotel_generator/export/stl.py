"""STL export via trimesh with shared vertices for watertight output."""

import io

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

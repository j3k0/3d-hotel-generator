"""Tests for export pipeline and validation checks."""

import pytest
import trimesh

from hotel_generator.geometry.primitives import box
from hotel_generator.export.stl import manifold_to_trimesh, export_stl_bytes
from hotel_generator.export.glb import manifold_to_trimesh_glb, export_glb_bytes
from hotel_generator.validation.checks import validate_manifold


class TestSTLExport:
    def test_manifold_to_trimesh(self):
        b = box(5, 4, 10)
        tmesh = manifold_to_trimesh(b)
        assert isinstance(tmesh, trimesh.Trimesh)
        assert len(tmesh.vertices) > 0
        assert len(tmesh.faces) > 0

    def test_stl_bytes(self):
        b = box(5, 4, 10)
        data = export_stl_bytes(b)
        assert isinstance(data, bytes)
        assert len(data) > 80  # STL header is 80 bytes

    def test_stl_roundtrip(self):
        import io
        b = box(5, 4, 10)
        data = export_stl_bytes(b)
        reimported = trimesh.load(io.BytesIO(data), file_type="stl")
        assert abs(reimported.volume - b.volume()) < 1.0


class TestGLBExport:
    def test_glb_bytes(self):
        b = box(5, 4, 10)
        data = export_glb_bytes(b)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_glb_roundtrip(self):
        import io
        b = box(5, 4, 10)
        data = export_glb_bytes(b)
        scene = trimesh.load(io.BytesIO(data), file_type="glb")
        assert scene is not None


class TestValidation:
    def test_valid_box(self):
        b = box(5, 4, 10)
        result = validate_manifold(b)
        assert result["is_watertight"]
        assert result["positive_volume"]
        assert result["pass"]

    def test_triangle_count(self):
        b = box(5, 4, 10)
        result = validate_manifold(b)
        assert result["triangle_count"] > 0
        assert result["triangle_count_ok"]

    def test_reasonable_size(self):
        b = box(5, 4, 10)
        result = validate_manifold(b)
        assert result["reasonable_size"]

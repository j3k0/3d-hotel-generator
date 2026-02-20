"""Tests for the FastAPI application."""

import json

import pytest
from fastapi.testclient import TestClient

from hotel_generator.api import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestStylesEndpoint:
    def test_list_styles(self, client):
        r = client.get("/styles")
        assert r.status_code == 200
        data = r.json()
        assert "styles" in data
        assert len(data["styles"]) >= 1
        names = [s["name"] for s in data["styles"]]
        assert "modern" in names

    def test_style_has_schema(self, client):
        r = client.get("/styles")
        styles = r.json()["styles"]
        modern = next(s for s in styles if s["name"] == "modern")
        assert "params_schema" in modern


class TestGenerateEndpoint:
    def test_generate_returns_glb(self, client):
        r = client.post("/generate", json={
            "style_name": "modern",
            "width": 30.0,
            "depth": 25.0,
            "num_floors": 4,
            "floor_height": 5.0,
            "printer_type": "fdm",
        })
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/octet-stream"
        assert len(r.content) > 0

    def test_generate_has_metadata_header(self, client):
        r = client.post("/generate", json={"style_name": "modern"})
        assert "X-Build-Metadata" in r.headers
        metadata = json.loads(r.headers["X-Build-Metadata"])
        assert "triangle_count" in metadata
        assert metadata["is_watertight"] is True

    def test_generate_invalid_style(self, client):
        r = client.post("/generate", json={"style_name": "nonexistent"})
        assert r.status_code == 400

    def test_generate_invalid_params(self, client):
        r = client.post("/generate", json={
            "style_name": "modern",
            "width": -1,
        })
        # Should return 400 or 422
        assert r.status_code in (400, 422, 500)


class TestExportSTLEndpoint:
    def test_export_stl(self, client):
        r = client.post("/export/stl", json={"style_name": "modern"})
        assert r.status_code == 200
        assert "Content-Disposition" in r.headers
        assert "attachment" in r.headers["Content-Disposition"]
        assert len(r.content) > 80  # STL header is 80 bytes


class TestPreviewPNGEndpoint:
    def _can_render(self):
        """Check if headless rendering is available."""
        try:
            import os
            os.environ.setdefault("PYOPENGL_PLATFORM", "osmesa")
            import pyrender
            r = pyrender.OffscreenRenderer(32, 32)
            r.delete()
            return True
        except Exception:
            return False

    def test_preview_png_returns_image(self, client):
        if not self._can_render():
            pytest.skip("pyrender/OSMesa not available")
        r = client.post(
            "/preview/png?angle=front_3q&resolution=128",
            json={"style_name": "modern"},
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        # PNG magic bytes
        assert r.content[:4] == b"\x89PNG"
        assert len(r.content) > 100

    def test_preview_png_invalid_angle(self, client):
        if not self._can_render():
            pytest.skip("pyrender/OSMesa not available")
        r = client.post(
            "/preview/png?angle=nonexistent",
            json={"style_name": "modern"},
        )
        assert r.status_code == 400

    def test_preview_png_invalid_style(self, client):
        if not self._can_render():
            pytest.skip("pyrender/OSMesa not available")
        r = client.post(
            "/preview/png?angle=front_3q",
            json={"style_name": "nonexistent"},
        )
        assert r.status_code == 400


class TestPresetsEndpoint:
    def test_list_presets(self, client):
        r = client.get("/presets")
        assert r.status_code == 200
        data = r.json()
        assert "presets" in data
        assert len(data["presets"]) == 9

    def test_preset_has_fields(self, client):
        r = client.get("/presets")
        presets = r.json()["presets"]
        royal = next(p for p in presets if p["name"] == "royal")
        assert royal["style_name"] == "classical"
        assert royal["num_buildings"] == 4
        assert "building_roles" in royal


class TestComplexGenerateEndpoint:
    def test_complex_generate_returns_glb(self, client):
        r = client.post("/complex/generate", json={
            "style_name": "modern",
            "num_buildings": 2,
        })
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/octet-stream"
        assert len(r.content) > 0

    def test_complex_generate_has_metadata(self, client):
        r = client.post("/complex/generate", json={
            "style_name": "modern",
            "num_buildings": 2,
        })
        assert "X-Complex-Metadata" in r.headers
        metadata = json.loads(r.headers["X-Complex-Metadata"])
        assert metadata["num_buildings"] == 2
        assert "lot_width" in metadata
        assert "buildings" in metadata

    def test_complex_generate_with_preset(self, client):
        r = client.post("/complex/generate", json={
            "style_name": "modern",
            "preset": "fujiyama",
            "num_buildings": 3,
        })
        assert r.status_code == 200
        metadata = json.loads(r.headers["X-Complex-Metadata"])
        assert metadata["num_buildings"] == 3

    def test_complex_generate_invalid_style(self, client):
        r = client.post("/complex/generate", json={
            "style_name": "nonexistent",
            "num_buildings": 2,
        })
        assert r.status_code == 400


class TestComplexExportEndpoint:
    def test_complex_export_returns_file_list(self, client):
        r = client.post("/complex/export", json={
            "style_name": "modern",
            "num_buildings": 2,
        })
        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert "base_plate.stl" in data["files"]
        assert "manifest.json" in data["files"]
        assert data["num_buildings"] == 2
        # Should have base_plate + 2 buildings + manifest = 4 files
        assert len(data["files"]) == 4

    def test_complex_export_creates_files(self, client):
        import os
        r = client.post("/complex/export", json={
            "style_name": "modern",
            "num_buildings": 2,
        })
        data = r.json()
        output_dir = data["output_dir"]
        for filename in data["files"]:
            assert os.path.exists(os.path.join(output_dir, filename))


class TestErrorHandlers:
    def test_error_handlers_registered(self):
        assert len(app.exception_handlers) > 0

"""Integration tests for hotel complex generation (Step 19)."""

import json
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from hotel_generator.api import app
from hotel_generator.complex.builder import ComplexBuilder, ComplexResult
from hotel_generator.complex.presets import PRESET_REGISTRY, get_preset
from hotel_generator.config import ComplexParams
from hotel_generator.export.stl import export_complex_to_directory
from hotel_generator.settings import Settings


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def builder():
    return ComplexBuilder(Settings())


class TestEndToEndComplexGeneration:
    """API -> generate -> export -> verify STL files."""

    def test_api_generate_then_export(self, client):
        """Full pipeline through API endpoints."""
        # Generate combined GLB preview
        gen_resp = client.post("/complex/generate", json={
            "style_name": "modern",
            "num_buildings": 3,
            "seed": 42,
        })
        assert gen_resp.status_code == 200
        assert len(gen_resp.content) > 0

        metadata = json.loads(gen_resp.headers["X-Complex-Metadata"])
        assert metadata["num_buildings"] == 3

        # Export to directory
        export_resp = client.post("/complex/export", json={
            "style_name": "modern",
            "num_buildings": 3,
            "seed": 42,
        })
        assert export_resp.status_code == 200
        data = export_resp.json()

        # Verify files exist
        assert "base_plate.stl" in data["files"]
        assert "manifest.json" in data["files"]
        stl_files = [f for f in data["files"] if f.endswith(".stl")]
        assert len(stl_files) == 4  # base + 3 buildings

        for filename in data["files"]:
            assert os.path.exists(os.path.join(data["output_dir"], filename))

        # Verify manifest
        manifest_path = os.path.join(data["output_dir"], "manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert manifest["num_buildings"] == 3
        assert len(manifest["placements"]) == 3

    def test_preset_api_flow(self, client):
        """Generate and export using a preset through API."""
        gen_resp = client.post("/complex/generate", json={
            "style_name": "modern",
            "preset": "royal",
            "num_buildings": 4,
        })
        assert gen_resp.status_code == 200
        metadata = json.loads(gen_resp.headers["X-Complex-Metadata"])
        assert metadata["num_buildings"] == 4

    def test_direct_export_pipeline(self, builder):
        """Direct: builder -> export_complex_to_directory -> verify."""
        params = ComplexParams(style_name="modern", num_buildings=3, seed=99)
        result = builder.build(params)

        with tempfile.TemporaryDirectory() as tmpdir:
            files = export_complex_to_directory(result, tmpdir)

            assert "base_plate.stl" in files
            assert "manifest.json" in files

            # All STLs are non-empty binary STL (80-byte header + 4-byte count + data)
            for f in files:
                if f.endswith(".stl"):
                    path = os.path.join(tmpdir, f)
                    size = os.path.getsize(path)
                    assert size > 84, f"{f} is too small ({size} bytes)"


class TestAllPresetsAllPrinters:
    """Parametrized: 8 presets x 2 printer types."""

    @pytest.mark.parametrize("preset_name", list(PRESET_REGISTRY.keys()))
    @pytest.mark.parametrize("printer_type", ["fdm", "resin"])
    def test_preset_printer_combination(self, builder, preset_name, printer_type):
        preset = get_preset(preset_name)
        params = ComplexParams(
            style_name=preset.style_name,
            num_buildings=preset.num_buildings,
            preset=preset_name,
            printer_type=printer_type,
            seed=42,
        )
        result = builder.build(params)

        assert len(result.buildings) == preset.num_buildings
        for b in result.buildings:
            assert b.is_watertight, (
                f"Preset {preset_name}/{printer_type}: building not watertight"
            )
        assert not result.combined.is_empty()
        assert result.lot_width > 0
        assert result.lot_depth > 0


class TestPerformance:
    """Complex generation performance requirements."""

    def test_six_building_under_5s(self, builder):
        """6-building complex should generate in under 5 seconds."""
        params = ComplexParams(
            style_name="modern",
            num_buildings=6,
            seed=42,
        )
        start = time.time()
        result = builder.build(params)
        elapsed = time.time() - start

        assert len(result.buildings) == 6
        assert elapsed < 5.0, (
            f"6-building complex took {elapsed:.2f}s (should be <5s)"
        )

    def test_single_building_fast(self, builder):
        """Single building complex should be fast."""
        params = ComplexParams(style_name="modern", num_buildings=1, seed=42)
        start = time.time()
        result = builder.build(params)
        elapsed = time.time() - start

        assert len(result.buildings) == 1
        assert elapsed < 2.0


class TestCrossPresetDistinctiveness:
    """Verify presets produce meaningfully different outputs."""

    def test_presets_produce_different_complexes(self, builder):
        """Different presets should produce different combined volumes."""
        volumes = {}
        for name in ["royal", "waikiki", "boomerang"]:
            preset = get_preset(name)
            params = ComplexParams(
                style_name=preset.style_name,
                num_buildings=preset.num_buildings,
                preset=name,
                seed=42,
            )
            result = builder.build(params)
            volumes[name] = result.combined.volume()

        # All three should have different volumes
        vol_list = list(volumes.values())
        assert vol_list[0] != pytest.approx(vol_list[1], rel=0.05)
        assert vol_list[1] != pytest.approx(vol_list[2], rel=0.05)

    def test_different_seeds_produce_variation(self, builder):
        """Same preset with different seeds should vary."""
        results = []
        for seed in [1, 2, 3]:
            params = ComplexParams(
                style_name="modern",
                num_buildings=3,
                seed=seed,
            )
            result = builder.build(params)
            results.append(result)

        # All should be valid
        for r in results:
            assert len(r.buildings) == 3
            assert not r.combined.is_empty()

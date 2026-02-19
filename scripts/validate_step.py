#!/usr/bin/env python3
"""
Per-step quality gate for autonomous agent workflow.

Run after completing each implementation step to verify it passes
before advancing to the next step. Returns exit code 0 on pass, 1 on fail.

Usage:
    python scripts/validate_step.py --step 2
    python scripts/validate_step.py --step 4 --verbose
"""
import argparse
import subprocess
import sys
import time

STEP_GATES = {
    1: {
        "description": "Scaffolding: errors, settings, conftest importable",
        "tests": [],
        "checks": [
            ("errors.py importable",
             "from hotel_generator.errors import HotelGeneratorError, InvalidParamsError, GeometryError"),
            ("settings.py importable",
             "from hotel_generator.settings import Settings; Settings()"),
            ("conftest exists",
             "import pathlib; assert pathlib.Path('tests/conftest.py').exists()"),
            ("set_circular_segments called",
             "import hotel_generator; from manifold3d import get_circular_segments; "
             "assert get_circular_segments(0.1) >= 16"),
        ],
    },
    2: {
        "description": "Geometry primitives: all primitives produce valid manifolds",
        "tests": ["tests/test_geometry.py"],
        "checks": [
            ("box produces valid manifold",
             "from hotel_generator.geometry.primitives import box; "
             "b = box(5, 4, 10); assert not b.is_empty(); assert b.volume() > 0"),
            ("cylinder produces valid manifold",
             "from hotel_generator.geometry.primitives import cylinder; "
             "c = cylinder(1.0, 5.0); assert not c.is_empty()"),
            ("union_all works",
             "from hotel_generator.geometry.primitives import box; "
             "from hotel_generator.geometry.booleans import union_all; "
             "r = union_all([box(1,1,1), box(2,2,2)]); assert not r.is_empty()"),
            ("safe_scale uses 3-vector",
             "from hotel_generator.geometry.transforms import safe_scale; "
             "from hotel_generator.geometry.primitives import box; "
             "b = box(1,1,1); s = safe_scale(b, 2, 2, 2); assert not s.is_empty()"),
        ],
    },
    3: {
        "description": "Components: each produces watertight geometry",
        "tests": ["tests/test_components.py"],
        "checks": [
            ("base slab with chamfer",
             "from hotel_generator.components.base import base_slab; "
             "b = base_slab(10, 8, 1.2, 0.3); assert b.volume() > 0"),
            ("flat roof",
             "from hotel_generator.components.roof import flat_roof; "
             "r = flat_roof(10, 8, 0.5); assert not r.is_empty()"),
            ("rect massing",
             "from hotel_generator.components.massing import rect_mass; "
             "m = rect_mass(10, 8, 15); assert m.volume() > 0"),
            ("window cutout overshoots",
             "from hotel_generator.components.window import window_cutout; "
             "w = window_cutout(0.5, 0.7, 0.8); assert w.volume() > 0"),
        ],
    },
    4: {
        "description": "Style system: config models, style registry, Modern style",
        "tests": ["tests/test_config.py", "tests/test_styles.py"],
        "checks": [
            ("BuildingParams validates",
             "from hotel_generator.config import BuildingParams; "
             "p = BuildingParams(style_name='modern', width=30.0, depth=25.0, "
             "num_floors=4, floor_height=5.0, printer_type='fdm')"),
            ("style registry has modern",
             "from hotel_generator.styles.base import STYLE_REGISTRY; "
             "assert 'modern' in STYLE_REGISTRY"),
            ("modern generates valid manifold",
             "from hotel_generator.styles.base import STYLE_REGISTRY; "
             "from hotel_generator.config import BuildingParams, PrinterProfile; "
             "style = STYLE_REGISTRY['modern']; "
             "params = BuildingParams(style_name='modern', width=30.0, depth=25.0, "
             "num_floors=4, floor_height=5.0, printer_type='fdm'); "
             "m = style.generate(params, PrinterProfile.fdm()); "
             "assert not m.is_empty(); assert m.volume() > 0"),
            ("assemble_building helper exists",
             "from hotel_generator.styles.base import assemble_building"),
        ],
    },
    5: {
        "description": "Assembly engine: HotelBuilder produces BuildResult",
        "tests": ["tests/test_assembly.py"],
        "checks": [
            ("HotelBuilder.build returns BuildResult",
             "from hotel_generator.assembly.building import HotelBuilder, BuildResult; "
             "from hotel_generator.config import BuildingParams; "
             "from hotel_generator.settings import Settings; "
             "builder = HotelBuilder(Settings()); "
             "params = BuildingParams(style_name='modern', width=30.0, depth=25.0, "
             "num_floors=4, floor_height=5.0, printer_type='fdm'); "
             "result = builder.build(params); "
             "assert isinstance(result, BuildResult); "
             "assert result.is_watertight; assert result.triangle_count > 0"),
        ],
    },
    6: {
        "description": "Export pipeline: STL + GLB + validation",
        "tests": ["tests/test_export.py"],
        "checks": [
            ("STL export produces bytes",
             "from hotel_generator.geometry.primitives import box; "
             "from hotel_generator.export.stl import export_stl_bytes; "
             "b = export_stl_bytes(box(5, 4, 10)); assert len(b) > 80"),
            ("GLB export produces bytes",
             "from hotel_generator.geometry.primitives import box; "
             "from hotel_generator.export.glb import export_glb_bytes; "
             "b = export_glb_bytes(box(5, 4, 10)); assert len(b) > 0"),
            ("validation checks work",
             "from hotel_generator.geometry.primitives import box; "
             "from hotel_generator.validation.checks import validate_manifold; "
             "result = validate_manifold(box(5, 4, 10)); "
             "assert result['is_watertight']"),
        ],
    },
    7: {
        "description": "API server: endpoints respond correctly",
        "tests": ["tests/test_api.py"],
        "checks": [
            ("FastAPI app importable",
             "from hotel_generator.api import app; "
             "assert app is not None"),
            ("error handlers registered",
             "from hotel_generator.api import app; "
             "assert len(app.exception_handlers) > 0"),
        ],
    },
    8: {
        "description": "Web UI: static files exist and are valid",
        "tests": [],
        "checks": [
            ("index.html exists",
             "import pathlib; assert pathlib.Path('web/index.html').exists()"),
            ("app.js exists",
             "import pathlib; assert pathlib.Path('web/app.js').exists()"),
            ("style.css exists",
             "import pathlib; assert pathlib.Path('web/style.css').exists()"),
            ("index.html has import map",
             "import pathlib; assert 'importmap' in pathlib.Path('web/index.html').read_text()"),
            ("app.js has HotelPreview class",
             "import pathlib; assert 'HotelPreview' in pathlib.Path('web/app.js').read_text() "
             "or 'class Hotel' in pathlib.Path('web/app.js').read_text()"),
        ],
    },
    9: {
        "description": "All 8 styles: generate valid, distinct buildings",
        "tests": ["tests/test_styles.py"],
        "checks": [
            ("all 8 styles registered",
             "from hotel_generator.styles.base import STYLE_REGISTRY; "
             "expected = {'modern','art_deco','classical','victorian',"
             "'mediterranean','tropical','skyscraper','townhouse'}; "
             "assert set(STYLE_REGISTRY.keys()) == expected, "
             "'Missing: ' + str(expected - set(STYLE_REGISTRY.keys()))"),
            ("all styles produce watertight geometry",
             "from hotel_generator.assembly.building import HotelBuilder\n"
             "from hotel_generator.config import BuildingParams\n"
             "from hotel_generator.settings import Settings\n"
             "builder = HotelBuilder(Settings())\n"
             "for style in ['modern','art_deco','classical','victorian',"
             "'mediterranean','tropical','skyscraper','townhouse']:\n"
             "    params = BuildingParams(style_name=style, width=30.0, depth=25.0,\n"
             "        num_floors=4, floor_height=5.0, printer_type='fdm')\n"
             "    result = builder.build(params)\n"
             "    assert result.is_watertight, style + ' not watertight'\n"),
        ],
    },
    10: {
        "description": "Polish: all tests pass, all styles valid on both printer types",
        "tests": ["tests/"],
        "checks": [
            ("all styles on FDM",
             "from hotel_generator.assembly.building import HotelBuilder\n"
             "from hotel_generator.config import BuildingParams\n"
             "from hotel_generator.settings import Settings\n"
             "builder = HotelBuilder(Settings())\n"
             "for style in ['modern','art_deco','classical','victorian',"
             "'mediterranean','tropical','skyscraper','townhouse']:\n"
             "    params = BuildingParams(style_name=style, width=30.0, depth=25.0,\n"
             "        num_floors=4, floor_height=5.0, printer_type='fdm', seed=42)\n"
             "    result = builder.build(params)\n"
             "    assert result.is_watertight\n"
             "    assert result.triangle_count < 200000\n"),
            ("all styles on resin",
             "from hotel_generator.assembly.building import HotelBuilder\n"
             "from hotel_generator.config import BuildingParams\n"
             "from hotel_generator.settings import Settings\n"
             "builder = HotelBuilder(Settings())\n"
             "for style in ['modern','art_deco','classical','victorian',"
             "'mediterranean','tropical','skyscraper','townhouse']:\n"
             "    params = BuildingParams(style_name=style, width=30.0, depth=25.0,\n"
             "        num_floors=4, floor_height=5.0, printer_type='resin', seed=42)\n"
             "    result = builder.build(params)\n"
             "    assert result.is_watertight\n"
             "    assert result.triangle_count < 200000\n"),
        ],
    },
    11: {
        "description": "Scale-aware dimensions: ScaleContext + updated validation",
        "tests": ["tests/"],
        "checks": [
            ("ScaleContext importable",
             "from hotel_generator.components.scale import ScaleContext; "
             "from hotel_generator.config import PrinterProfile; "
             "sc = ScaleContext(30, 25, 5.0, 4, PrinterProfile.fdm()); "
             "assert sc.window_width > 0; assert sc.door_width > 0"),
            ("ScaleContext scales with floor_height",
             "from hotel_generator.components.scale import ScaleContext; "
             "from hotel_generator.config import PrinterProfile; "
             "sc_small = ScaleContext(10, 8, 2.0, 4, PrinterProfile.fdm()); "
             "sc_large = ScaleContext(30, 25, 5.0, 4, PrinterProfile.fdm()); "
             "assert sc_large.window_width > sc_small.window_width"),
            ("all styles use ScaleContext at new scale",
             "from hotel_generator.assembly.building import HotelBuilder\n"
             "from hotel_generator.config import BuildingParams\n"
             "from hotel_generator.settings import Settings\n"
             "builder = HotelBuilder(Settings())\n"
             "for style in ['modern','art_deco','classical','victorian',"
             "'mediterranean','tropical','skyscraper','townhouse']:\n"
             "    params = BuildingParams(style_name=style, width=30.0, depth=25.0,\n"
             "        num_floors=4, floor_height=5.0, printer_type='fdm')\n"
             "    result = builder.build(params)\n"
             "    assert result.is_watertight, style + ' not watertight'\n"),
            ("new defaults are hotel scale",
             "from hotel_generator.config import BuildingParams, PrinterProfile; "
             "p = BuildingParams(style_name='modern'); "
             "assert p.width == 30.0; assert p.floor_height == 5.0; "
             "prof = PrinterProfile.fdm(); "
             "assert prof.base_thickness == 2.5"),
        ],
    },
    12: {
        "description": "ComplexParams config model",
        "tests": ["tests/test_config.py"],
        "checks": [
            ("BuildingPlacement importable",
             "from hotel_generator.config import BuildingPlacement; "
             "p = BuildingPlacement(x=5.0, y=3.0, role='wing'); "
             "assert p.role == 'wing'"),
            ("ComplexParams validates",
             "from hotel_generator.config import ComplexParams; "
             "p = ComplexParams(style_name='modern', num_buildings=4); "
             "assert p.num_buildings == 4; assert p.building_spacing == 5.0"),
            ("ComplexParams rejects invalid",
             "from hotel_generator.config import ComplexParams; "
             "from hotel_generator.errors import InvalidParamsError; "
             "from pydantic import ValidationError; "
             "ok = False\n"
             "try:\n"
             "    ComplexParams(style_name='modern', num_buildings=7)\n"
             "except (ValidationError, InvalidParamsError):\n"
             "    ok = True\n"
             "assert ok, 'Should reject num_buildings=7'"),
            ("PresetInfo importable",
             "from hotel_generator.config import PresetInfo; "
             "p = PresetInfo(name='royal', display_name='Royal', "
             "description='Grand', style_name='classical', "
             "num_buildings=4, building_roles=['main','wing','wing','tower']); "
             "assert len(p.building_roles) == 4"),
        ],
    },
    13: {
        "description": "Layout engine: 6 strategies + overlap detection",
        "tests": ["tests/test_layout.py"],
        "checks": [
            ("6 strategies registered",
             "from hotel_generator.layout.strategies import STRATEGIES; "
             "assert len(STRATEGIES) == 6; "
             "assert 'row' in STRATEGIES; assert 'courtyard' in STRATEGIES"),
            ("LayoutEngine produces valid layout",
             "from hotel_generator.layout.engine import LayoutEngine; "
             "from hotel_generator.config import ComplexParams; "
             "engine = LayoutEngine(); "
             "params = ComplexParams(style_name='modern', num_buildings=4); "
             "placements = engine.compute_layout(params, strategy='row'); "
             "assert len(placements) == 4"),
            ("all styles have preferred strategy",
             "from hotel_generator.styles.base import STYLE_REGISTRY\n"
             "from hotel_generator.layout.strategies import STRATEGIES\n"
             "for name, style in STYLE_REGISTRY.items():\n"
             "    s = style.preferred_layout_strategy()\n"
             "    assert s in STRATEGIES, name + ' has invalid strategy ' + s\n"),
        ],
    },
    14: {
        "description": "ComplexBuilder: multi-building generation",
        "tests": ["tests/test_complex.py", "tests/test_assembly.py"],
        "checks": [
            ("ComplexBuilder produces valid complex",
             "from hotel_generator.complex.builder import ComplexBuilder, ComplexResult\n"
             "from hotel_generator.config import ComplexParams\n"
             "from hotel_generator.settings import Settings\n"
             "builder = ComplexBuilder(Settings())\n"
             "result = builder.build(ComplexParams(style_name='modern', num_buildings=3))\n"
             "assert isinstance(result, ComplexResult)\n"
             "assert len(result.buildings) == 3\n"
             "assert not result.combined.is_empty()\n"),
            ("skip_base works",
             "from hotel_generator.assembly.building import HotelBuilder\n"
             "from hotel_generator.config import BuildingParams\n"
             "from hotel_generator.settings import Settings\n"
             "builder = HotelBuilder(Settings())\n"
             "r = builder.build(BuildingParams(style_name='modern'), skip_base=True)\n"
             "assert r.is_watertight\n"),
        ],
    },
}


def run_tests(test_paths: list[str], verbose: bool = False) -> tuple[bool, str]:
    """Run pytest on the given paths. Returns (success, output)."""
    if not test_paths:
        return True, "No tests specified for this step"

    cmd = ["python", "-m", "pytest", "-x", "-q", "--tb=short"] + test_paths
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def run_checks(checks: list[tuple[str, str]], verbose: bool = False) -> tuple[bool, list[str]]:
    """Run inline Python checks. Returns (all_passed, failure_messages)."""
    failures = []
    for name, code in checks:
        try:
            exec(code, {})
            if verbose:
                print(f"  PASS: {name}")
        except Exception as e:
            failures.append(f"  FAIL: {name}\n    {type(e).__name__}: {e}")
    return len(failures) == 0, failures


def validate_step(step: int, verbose: bool = False) -> bool:
    """Validate a single step. Returns True if passed."""
    if step not in STEP_GATES:
        print(f"ERROR: Unknown step {step}. Valid steps: {sorted(STEP_GATES.keys())}")
        return False

    gate = STEP_GATES[step]
    print(f"\n{'='*60}")
    print(f"Step {step}: {gate['description']}")
    print(f"{'='*60}\n")

    # Run tests
    print("Running tests...")
    start = time.time()
    tests_ok, test_output = run_tests(gate["tests"], verbose)
    elapsed = time.time() - start

    if not tests_ok:
        print(f"FAIL: Tests failed ({elapsed:.1f}s)")
        print(test_output)
        return False
    print(f"  Tests passed ({elapsed:.1f}s)")

    # Run checks
    print("Running quality checks...")
    checks_ok, failures = run_checks(gate["checks"], verbose)

    if not checks_ok:
        print("FAIL: Quality checks failed:")
        for f in failures:
            print(f)
        return False
    print(f"  All {len(gate['checks'])} checks passed")

    print(f"\n{'='*60}")
    print(f"PASS: Step {step} validated")
    print(f"{'='*60}\n")
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate implementation step quality gate")
    parser.add_argument("--step", type=int, required=True, help="Step number to validate (1-10)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show individual check results")
    args = parser.parse_args()

    success = validate_step(args.step, args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

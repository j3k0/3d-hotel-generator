# CLAUDE.md -- Agent Development Instructions

## Project Overview
Procedural 3D hotel generator. Python backend with manifold3d CSG, FastAPI server,
three.js web frontend. Generates 3D-printable Monopoly-scale hotel game pieces (~1-2cm
tall) as STL files with a web preview UI.

## Key Commands
```bash
# Install (editable, with dev + render extras)
pip install -e ".[dev,render]"

# Run all tests
pytest tests/ -x -q

# Run tests for a specific step
pytest tests/test_geometry.py -x -q

# Validate a completed step (binary pass/fail gate)
python scripts/validate_step.py --step N

# Run server
uvicorn hotel_generator.api:app --reload

# Render a single style (headless, no display needed)
PYOPENGL_PLATFORM=osmesa python scripts/render_hotel.py --style modern --seed 42

# Render all 8 styles in a comparison grid
PYOPENGL_PLATFORM=osmesa python scripts/render_style_grid.py

# Run vision model critique on a style (requires ANTHROPIC_API_KEY)
python scripts/critique_hotel.py --style modern --seed 42

# Generate reference renders for all styles (CI)
PYOPENGL_PLATFORM=osmesa python scripts/generate_all_styles.py --output-dir renders/
```

## Implementation Order
Follow `plan.md` steps 1-10 in strict order. Do NOT skip ahead.

After completing each step:
1. Run `pytest tests/ -x -q` to verify all tests pass
2. Run `python scripts/validate_step.py --step N` for quality gate
3. Only proceed to step N+1 after step N passes
4. Commit after each passing step

After implementing each style (Steps 4 and 9):
1. Run `python scripts/render_hotel.py --style <name>` to generate renders
2. Run `python scripts/critique_hotel.py --style <name>` for vision model feedback
3. If critique score < 4.0, read suggestions, modify style code, re-render (max 3 iterations)
4. After all 8 styles: run `python scripts/render_style_grid.py` and critique the grid for distinctiveness

Style implementation order (Step 9, increasing complexity):
Art Deco -> Classical -> Skyscraper -> Townhouse -> Mediterranean -> Tropical -> Victorian

## Critical Rules

### manifold3d
1. ALL `scale()` calls MUST use 3-vector form via `safe_scale()`.
   Scalar `scale(float)` crashes Python bindings in v3.3.2.
2. Call `manifold3d.set_circular_segments(16)` in `src/hotel_generator/__init__.py`.
   Default produces 4 segments for small radii.
3. All boolean cutouts MUST overshoot by `BOOLEAN_OVERSHOOT` (0.1mm).
4. All additive features MUST embed by `BOOLEAN_EMBED` (0.1mm).
5. Check for empty manifold after EVERY CSG phase. Empty manifolds propagate silently.
6. `Manifold.compose()` is O(1) but ONLY for non-overlapping solids.
   Use `batch_boolean` for overlapping geometry.
7. `batch_boolean` with empty list crashes. Filter empty manifolds first.
8. Pin version: `manifold3d>=3.3.2,<4.0`.

### FastAPI
9. Generation endpoints MUST be sync `def` not `async def` (CPU-bound manifold3d work).
10. Register API routes BEFORE static file mount.

### Pydantic
11. Use Pydantic v2 syntax: `model_validator`, not `root_validator`.

### Randomness
12. ALL randomness must flow through a single `random.Random(seed)` instance
    passed into style generators. Never use bare `random.random()` or `numpy.random`.

## Target Dimensions at Print Scale
```
Total height:    10-20mm (including base and roof)
Footprint:       5-10mm x 4-8mm
Base slab:       extends 0.5mm beyond building on each side
Floor height:    0.6-1.0mm per floor
Window:          0.3-0.5mm wide, 0.4-0.7mm tall, 0.15-0.3mm deep recess
Wall thickness:  0.8mm FDM / 0.5mm resin
Column diameter: 0.8mm FDM / 0.4mm resin
```

## File Organization
- `geometry/` — Pure geometry functions. No style knowledge.
- `components/` — Reusable building parts. No style knowledge.
- `styles/` — Combine components. Know about architecture.
- `assembly/` — Orchestration only. No geometry construction.
- `validation/` — Post-hoc checks on built geometry.
- `scripts/` — Agent utilities: validation gates, rendering, critique.

## When Stuck

### CSG produces empty manifold
1. Print bounding box of all inputs: `print(solid.bounding_box())`
2. Check for zero-dimension inputs (width/height/depth <= 0)
3. Check for coplanar faces — add `COPLANAR_OFFSET` (0.01mm)
4. Check cutout doesn't exceed body (subtraction removed everything)
5. Simplify: test with just 2 manifolds, then add complexity

### Boolean subtraction gives unexpected result
1. Ensure cutout overshoots the surface by 0.1mm on both sides
2. Ensure cutout volume overlaps with the target (check bounding boxes)
3. Print volumes before/after: `print(solid.volume())`

### trimesh reports non-watertight
1. manifold3d output is always watertight — check the conversion step
2. Use `mesh.vert_properties[:, :3]` for vertices (not all columns)
3. Use `mesh.tri_verts` for faces
4. Ensure correct numpy dtypes: vertices `float32`/`float64`, faces `int32`/`uint32`

### Style doesn't look right
1. Run `python scripts/render_hotel.py --style X` and examine output
2. Compare against `docs/architectural-styles.md` description
3. Check: correct roof type? correct massing shape? windows present?
4. Fix massing first (overall shape), then details (windows, decorations)
5. Use `python scripts/critique_hotel.py --style X` for specific suggestions

### Import error for manifold3d
```bash
pip install "manifold3d>=3.3.2,<4.0"
```

## Failure Recovery Protocol

### Test Failure
1. Read the full traceback
2. Identify whether it's a code bug or a test bug
3. If code bug: fix the source, re-run tests
4. If test bug: fix the test expectation (only if the test was wrong)
5. Max 5 fix attempts per failure. After 5, add a TODO comment and move on.

### Geometry Bug (empty manifold, non-watertight)
1. Debug with: `from hotel_generator.geometry.primitives import debug_manifold`
2. Print bounding box and volume of all inputs
3. Check for zero-dimension inputs
4. Check for coplanar faces (add COPLANAR_OFFSET)
5. Simplify: test with just 2 manifolds, then add complexity

### Style Doesn't Look Right (visual feedback loop)
1. Render from 4 angles
2. Compare against docs/architectural-styles.md description
3. Check: correct roof type? correct massing shape? windows present?
4. If fundamentally wrong shape: fix massing first, then details
5. If details missing: add one feature at a time, re-render each time
6. Max 3 critique iterations per style before flagging for human review

## Reference Materials
- `plan.md` — Full implementation plan with steps and architecture
- `docs/geometry-library-evaluation.md` — manifold3d API reference and pitfalls
- `docs/3d-printing-constraints.md` — All printability constraints and profiles
- `docs/architectural-styles.md` — Style descriptions with CSG pseudocode
- `docs/procedural-generation.md` — Algorithms for facades, roofs, massing
- `docs/software-architecture.md` — Module design patterns
- `docs/web-ui-architecture.md` — three.js setup, controls, responsive layout
- `docs/board-game-history.md` — Game piece ergonomics and design constraints

## manifold3d 3.3.2 Known Issues
- `scale(float)` crashes Python bindings — use `scale([sx, sy, sz])`
- Small radii with default circular_segments produce 4-sided "cylinders"
- `batch_boolean` with empty list crashes — filter first
- `Manifold.compose()` is O(1) but only for non-overlapping solids
- Empty manifold propagates silently through all operations — always check

# 3D Hotel Generator - Implementation Plan

## Project Goal
Build a Python tool that procedurally generates 3D-printable hotel game pieces (Monopoly-style, ~1-2cm tall) as STL files, with a web UI for previewing and customizing buildings.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Web UI (three.js)                  │
│   Style selector → Param sliders → GLB preview      │
│   Loading/error states → Download STL                │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP API (FastAPI)
┌──────────────────────▼──────────────────────────────┐
│                 Python Backend                        │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────┐ │
│  │  Style      │ │ Component  │ │   Assembly       │ │
│  │  Grammars   │ │ Generators │ │   (CSG boolean)  │ │
│  └────────────┘ └────────────┘ └──────────────────┘ │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────┐ │
│  │  manifold3d │ │  trimesh   │ │   Validation     │ │
│  │  (geometry) │ │  (export)  │ │   (printability) │ │
│  └────────────┘ └────────────┘ └──────────────────┘ │
│  ┌────────────┐ ┌────────────┐                       │
│  │  errors.py  │ │ settings.py│                       │
│  │  (hierarchy)│ │ (env conf) │                       │
│  └────────────┘ └────────────┘                       │
└─────────────────────────────────────────────────────┘
```

## Core Libraries

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| **manifold3d** | >=3.3.2, <4.0 | CSG geometry engine | Guaranteed watertight output, fast booleans, lightweight (~1.2MB) |
| **trimesh** | >=4.0, <5.0 | Mesh I/O & validation | STL/GLB export, watertightness checks |
| **numpy** | >=1.24, <3.0 | Array ops | Required by both above |
| **fastapi** | >=0.100, <1.0 | Web API | Auto-docs, lightweight |
| **uvicorn** | >=0.20 | ASGI server | Run FastAPI |
| **pydantic** | >=2.0, <3.0 | Config models | Param validation, serialization |
| **pydantic-settings** | >=2.0 | Environment config | Server settings from env vars |

Total install: ~30MB (vs ~200MB+ for OpenCascade-based alternatives).

---

## Project Structure

```
3d-hotel-generator/
├── pyproject.toml
├── README.md
├── src/
│   └── hotel_generator/
│       ├── __init__.py
│       ├── errors.py              # Custom exception hierarchy
│       ├── settings.py            # Env-based config (pydantic-settings)
│       ├── geometry/
│       │   ├── __init__.py
│       │   ├── primitives.py      # box, cylinder, cone, extrude, revolve (with guards)
│       │   ├── booleans.py        # batch_union, batch_difference, compose
│       │   └── transforms.py      # translate, rotate, mirror, safe_scale
│       ├── components/
│       │   ├── __init__.py
│       │   ├── base.py            # Base/pedestal slab with chamfer
│       │   ├── wall.py            # Wall with thickness
│       │   ├── window.py          # Window cutout + optional frame
│       │   ├── door.py            # Door cutout + canopy
│       │   ├── roof.py            # Flat, gabled, hipped, mansard, barrel
│       │   ├── balcony.py         # Floor slab + railing
│       │   ├── column.py          # Round/square columns, pilasters
│       │   ├── floor_slab.py      # Per-floor horizontal slab
│       │   ├── massing.py         # Floor plan shapes: rect, L, U, T, podium+tower, stepped
│       │   └── facade.py          # Compose windows/doors onto a wall
│       ├── styles/
│       │   ├── __init__.py
│       │   ├── base.py            # Abstract style + style registry + assemble_building()
│       │   ├── modern.py
│       │   ├── classical.py
│       │   ├── art_deco.py
│       │   ├── victorian.py
│       │   ├── mediterranean.py
│       │   ├── tropical.py
│       │   ├── skyscraper.py
│       │   └── townhouse.py
│       ├── assembly/
│       │   ├── __init__.py
│       │   └── building.py        # HotelBuilder orchestrator → BuildResult
│       ├── export/
│       │   ├── __init__.py
│       │   ├── stl.py             # Binary STL via trimesh (shared verts, watertight)
│       │   └── glb.py             # GLB with calculate_normals() for web preview
│       ├── validation/
│       │   ├── __init__.py
│       │   └── checks.py          # 10-point validation checklist
│       ├── config.py              # Pydantic models: BuildingParams, response models
│       └── api.py                 # FastAPI endpoints + error handlers + CORS
├── web/
│   ├── index.html                 # Single-page app with import map for three.js
│   ├── app.js                     # HotelPreview class + ParameterUI + API integration
│   └── style.css                  # Dark theme, responsive grid layout
└── tests/
    ├── conftest.py                # Shared fixtures: fdm_constraints, default_params, builder
    ├── test_geometry.py
    ├── test_components.py
    ├── test_config.py
    ├── test_styles.py
    ├── test_assembly.py
    ├── test_export.py
    └── test_api.py
```

---

## Implementation Steps (in order)

### Step 1: Project scaffolding + core infrastructure
- Create `pyproject.toml` with pinned dependencies (upper bounds)
- Create package structure (`src/hotel_generator/` with `__init__.py` files)
- Create `.gitignore`
- `errors.py` — Custom exception hierarchy:
  - `HotelGeneratorError` (base)
  - `InvalidParamsError` (bad user input → 400)
  - `GeometryError` (CSG failure → 500)
  - `ValidationError` (post-generation check failure → 500)
- `settings.py` — `Settings(BaseSettings)` with `HOTEL_` prefix:
  - `host`, `port`, `cors_origins`, `log_level`, `max_triangles`
- `tests/conftest.py` — shared pytest fixtures:
  - `fdm_constraints`, `resin_constraints`, `default_params`, `builder`
- Global setup: `set_circular_segments(16)` at module init to prevent
  4-segment circles for small radii
- Logging configuration: Python `logging` module, structured output

### Step 2: Geometry primitives layer
- `geometry/primitives.py`:
  - `box(w, d, h)` — guard against zero/negative dimensions
  - `cylinder(r, h, segments)` — guard against zero radius
  - `cone(r_bottom, r_top, h, segments)` — tapered cylinder
  - `extrude_polygon(points, height)` — CrossSection → extrude
  - `revolve_profile(points, segments, degrees)` — for domes, barrel roofs
  - All primitives validate dimensions > 0 before construction, raise `GeometryError` on invalid input
- `geometry/booleans.py`:
  - `union_all(parts)` — `Manifold.batch_boolean(parts, OpType.Add)`, filter empty manifolds first
  - `difference_all(base, cutouts)` — `Manifold.batch_boolean([base] + cutouts, OpType.Subtract)`
  - `compose_disjoint(parts)` — `Manifold.compose(parts)` for non-overlapping (O(1))
  - Empty-manifold check after each phase to catch silent propagation
- `geometry/transforms.py`:
  - `translate(solid, x, y, z)`
  - `rotate_z(solid, degrees)`, `rotate_x(...)`, `rotate_y(...)`
  - `mirror_x(solid)`, `mirror_y(solid)`
  - `safe_scale(solid, sx, sy, sz)` — always uses 3-vector form (scalar `scale(float)` crashes Python bindings in manifold3d 3.3.2)
- Key rules:
  - All cutouts overshoot by `BOOLEAN_OVERSHOOT = 0.1mm`
  - All additive features embed by `BOOLEAN_EMBED = 0.1mm`
- **Tests** (`test_geometry.py`):
  - Each primitive produces a valid, non-empty manifold
  - Boolean operations maintain watertightness
  - Zero-dimension inputs raise `GeometryError`
  - `safe_scale` with scalar value works correctly
  - Empty manifold filtering works in `union_all`

### Step 3: Building components
- `components/base.py` — **Base/pedestal slab** (critical for printability and gameplay):
  - Parametric footprint (slightly larger than building)
  - Configurable thickness: 1.2mm FDM / 1.0mm resin
  - 45° chamfer on bottom edge (0.3mm FDM / 0.2mm resin) for elephant's foot
  - Walls overlap into base by 0.1mm (BOOLEAN_EMBED)
- `components/massing.py` — **Floor plan shapes** (needed by 5+ styles):
  - `rect_mass(w, d, h)` — simple box
  - `l_shape_mass(...)` — for Victorian, Modern, Tropical
  - `u_shape_mass(...)` — for Mediterranean (courtyard)
  - `t_shape_mass(...)` — for Classical variants
  - `podium_tower_mass(...)` — for Skyscraper
  - `stepped_mass(...)` — for Art Deco (ziggurat)
  - All return `Manifold` with base at z=0
- `components/wall.py` — Solid box with parametric width/height/thickness
- `components/window.py`:
  - Cutout solid + optional frame (frame only if printer profile allows)
  - Rectangular (all printers) and arched (resin-only) variants
  - Frame embedded 0.1mm into wall when present
- `components/door.py` — Cutout solid + optional canopy with 45° underside
- `components/roof.py` — Generators for:
  - Flat (with parapet)
  - Gabled (via CrossSection triangle extrusion)
  - Hipped (four angled planes via intersection)
  - Mansard (hull of two rects + low gable on top)
  - Barrel (via `revolve_profile`, 180° half-cylinder)
  - All roofs overlap wall tops by 0.1mm
- `components/balcony.py` — Floor slab + simple railing (solid wall for FDM, balusters for resin)
  - 45° support wedge underneath for FDM (overhang mitigation)
- `components/column.py` — Round cylinder or square pilaster
  - Square preferred for FDM (prints more reliably at small diameters)
- `components/floor_slab.py` — Horizontal divider with optional groove
- `components/facade.py` — Place windows/doors on a wall at computed grid positions
- **Tests** (`test_components.py`):
  - Each component produces a watertight manifold
  - Base chamfer geometry is valid
  - Massing shapes for all plan types produce correct bounding boxes
  - Window cutouts overshoot correctly
  - Roof generators produce valid geometry for typical parameter ranges

### Step 4: Config models + style system foundation
- `config.py` — Pydantic models:
  - `PrinterProfile` — dataclass with all constraint values (see Printing Constraints table below)
  - `BuildingParams`:
    - Dimensions: `width`, `depth`, `num_floors`, `floor_height`
    - Style: `style_name`, `printer_type` ("fdm" | "resin")
    - Optional: `seed` (int, for reproducible generation), `max_triangles` (default 50000)
    - `style_params: dict[str, Any]` — style-specific overrides
    - `model_validator`: reject aspect ratios above 8:1
    - `model_validator`: ensure windows fit in wall dimensions
  - Response models:
    - `StyleInfo` — name, display_name, description, params_schema
    - `GenerateResponse` — used for metadata in X-Build-Metadata header
    - `ErrorResponse` — error type, message, detail
- `styles/base.py`:
  - `HotelStyle` ABC:
    - `name: str`, `display_name: str`, `description: str`
    - `generate(params: BuildingParams, profile: PrinterProfile) -> Manifold`
    - `style_params_schema() -> dict` — JSON Schema for style-specific params
    - `validate_style_params(params: dict) -> dict` — validate + clean style params, raises `InvalidParamsError`
  - `assemble_building()` — **shared three-phase CSG helper**:
    ```
    def assemble_building(shell, cutouts, additions, cleanup_cuts=None) -> Manifold:
        Phase 1: shell - union_all(cutouts)
        Phase 2: + union_all(additions)
        Phase 3: - union_all(cleanup_cuts)  # optional
        Empty-manifold check after each phase
    ```
    Styles call this instead of managing CSG booleans directly.
    Reduces duplication across 8 styles.
  - `STYLE_REGISTRY: dict[str, HotelStyle]` — auto-populated via decorator
  - `list_styles() -> list[StyleInfo]`
- `styles/modern.py` — First style implementation:
  - Flat roof, grid windows, optional cantilever, penthouse box
  - Uses `assemble_building()` helper
  - Validates its own `style_params` (window_style, has_penthouse, etc.)
- **Tests** (`test_config.py`, `test_styles.py`):
  - `test_config.py`: valid params accepted, aspect ratio >8:1 rejected, windows-too-large rejected, boundary conditions
  - `test_styles.py`: Modern style generates valid watertight manifold, style registry works, `validate_style_params` catches bad input

### Step 5: Assembly engine
- `assembly/building.py`:
  - `BuildResult` dataclass:
    - `manifold: Manifold`
    - `triangle_count: int`
    - `bounding_box: tuple`
    - `is_watertight: bool`
    - `warnings: list[str]`
    - `metadata: dict` (generation time, style, params hash)
  - `HotelBuilder`:
    - `__init__(settings: Settings)` — injectable for testing
    - `build(params: BuildingParams) -> BuildResult`:
      1. Resolve `PrinterProfile` from `params.printer_type`
      2. Look up style in registry, call `validate_style_params()`
      3. Create seeded RNG from `params.seed`
      4. Call `style.generate(params, profile)` → `Manifold`
      5. Add base/pedestal component
      6. Simplify if triangle count exceeds `params.max_triangles` (via `.as_original().simplify()`)
      7. Run validation checks
      8. Return `BuildResult` with metadata
  - Orchestration only — does NOT do geometry construction (that's the style's job)
  - Responsibility boundary: Builder = orchestrate + validate; Style = construct geometry
- **Tests** (`test_assembly.py`):
  - Full pipeline produces watertight mesh
  - Builder returns correct BuildResult fields
  - Triangle count simplification triggers when exceeded
  - Invalid style name raises `InvalidParamsError`

### Step 6: Export pipeline
- `export/stl.py`:
  - `manifold_to_trimesh(solid)` → `trimesh.Trimesh` (shared vertices, watertight)
  - `export_stl_bytes(solid)` → `bytes` (binary STL)
  - Use `to_mesh()` without normals for STL
- `export/glb.py`:
  - `manifold_to_trimesh_glb(solid, sharp_angle=50.0)` → `trimesh.Trimesh` with vertex normals
  - Uses `calculate_normals(normal_idx=0, min_sharp_angle=50)` then `to_mesh(normal_idx=0)`
  - Split vertices at sharp edges — expected for rendering, not for printing
  - `export_glb_bytes(solid)` → `bytes`
- `validation/checks.py` — 10-point validation checklist:
  1. Watertight: `trimesh.Trimesh.is_watertight == True`
  2. Positive volume: `volume > 0`
  3. Correct orientation: bounding box `min_z >= -0.001` (base at Z=0)
  4. Reasonable size: fits within 25mm × 25mm × 30mm
  5. Not too small: exceeds 5mm in all dimensions
  6. Triangle count: between 100 and 200,000
  7. No degenerate triangles: all areas > 1e-10 mm²
  8. Consistent normals: all face normals point outward
  9. Single connected component: one piece, not floating parts
  10. Minimum wall thickness: sample-based check (optional, expensive)
- **Tests** (`test_export.py`):
  - STL export produces valid binary STL bytes
  - GLB export produces valid GLB bytes with normals
  - Validation catches non-watertight, zero-volume, oversized meshes
  - Round-trip: generate → export → reimport → validate

### Step 7: API server
- `api.py` — FastAPI app:
  - **Endpoints** (all sync `def`, NOT `async def` — manifold3d is CPU-bound, sync lets FastAPI auto-delegate to thread pool):
    - `POST /generate` — Accept `BuildingParams` JSON, return GLB bytes
      - Response: `application/octet-stream` with `X-Build-Metadata` header (JSON: triangle_count, warnings, bbox)
    - `POST /export/stl` — Accept `BuildingParams` JSON, return STL file download
      - Response: `application/octet-stream` with `Content-Disposition: attachment`
    - `GET /styles` — List styles with display names, descriptions, and JSON Schema for params
      - Returns `{ "styles": [{ "name", "display_name", "description", "params_schema" }] }`
    - `GET /health` — Health check (this one can be `async def`)
  - **Error handling**:
    - Register FastAPI exception handlers mapping domain errors to HTTP status codes:
      - `InvalidParamsError` → 400 with `ErrorResponse` body
      - Pydantic `ValidationError` → 422 (FastAPI default)
      - `GeometryError` → 500 with `ErrorResponse` body
      - Unhandled → 500 generic
    - Log full tracebacks for 500 errors via `logger.exception()`
  - **CORS middleware**: configured from `Settings.cors_origins` (needed for dev when UI served from different port)
  - **Dependency injection**: `get_builder()` function via FastAPI `Depends`, provides `HotelBuilder` instance (overridable in tests)
  - **Static files**: `app.mount("/", StaticFiles(directory="web", html=True))` — must be registered AFTER API routes
- **Tests** (`test_api.py`):
  - `/generate` returns GLB bytes with correct content type
  - `/generate` with invalid params returns 400
  - `/export/stl` returns binary STL with Content-Disposition
  - `/styles` returns list with schemas
  - `/health` returns 200

### Step 8: Web UI
The web UI is a single-page application with no build step. three.js loaded via import map from CDN.

**`web/index.html`:**
- Import map pinning three.js version (e.g., 0.170.0)
- CSS Grid layout: top bar + workspace (viewport + sidebar)
- Loading overlay with spinner over viewport
- Error toast area
- Style selector dropdown + dynamic params container in sidebar
- Download STL + Reset View buttons in top bar
- Responsive: sidebar collapses below viewport on narrow screens (`@media max-width: 768px`)

**`web/app.js` — HotelPreview class:**
- Scene setup:
  - `MeshStandardMaterial` (warm neutral color, roughness 0.65, non-metallic) applied to all meshes — backend GLB has no materials
  - 3-point lighting: key (directional + shadows), fill (opposite side), rim (behind)
  - Ambient + hemisphere lights for soft fill
  - Ground plane with shadow reception
  - Grid helper for scale reference
- GLB loading:
  - Use `GLTFLoader.parse(arrayBuffer, '')` — NOT `.load(url)` — because response comes from POST
  - Apply architectural material to all meshes in loaded scene
  - `EdgesGeometry` with 30° threshold for architectural edge highlighting
- Model replacement:
  - `disposeObject()` — traverse and dispose all geometries + materials to prevent GPU memory leaks
  - Remove old model from scene before adding new one
- Auto-framing:
  - Compute bounding box of new model
  - Reposition orbit target to model center
  - Adjust camera distance based on FOV and model size
  - Update near/far planes
- Viewport resize: `ResizeObserver` on container (NOT window resize event — container can resize independently)

**`web/app.js` — ParameterUI class:**
- Build controls dynamically from `/styles` JSON Schema response
- Map JSON Schema types to HTML controls:
  - `number`/`integer` with min/max → range slider + value display
  - `string` with `enum` → dropdown select
  - `boolean` → checkbox
- Store current param values, call `onChange` callback on any change

**`web/app.js` — API integration:**
- Debounced preview requests (300ms delay after last slider change)
- `AbortController` to cancel in-flight requests when newer request supersedes
- Generation counter to guard against stale responses arriving out of order
- Request deduplication: skip if params hash matches last request
- Loading state: show spinner overlay, dim (but don't hide) current model
- Error handling:
  - Network errors → toast message (auto-dismiss after 5s)
  - 400/422 → parse error body, show field-specific validation messages
  - GLB parse errors → "Model load failed" toast, retain previous model
- STL download: POST to `/export/stl`, trigger download via ephemeral `<a>` element, disable button during request

**`web/app.js` — OrbitControls:**
- Target vertical center of model (~8mm above ground)
- Damping enabled (0.08)
- Zoom limits: 10 (closest) to 120 (furthest)
- Polar angle limits: near top-down to just above horizon (prevent going below ground)
- Pan constrained to ±20mm box
- Touch support for tablet

**`web/style.css`:**
- Dark theme (`#1a1d23` background)
- CSS Grid: 48px top bar + workspace (1fr viewport + 320px sidebar)
- Styled sliders, selects, checkboxes with accent color
- Loading spinner animation
- Error toast styling
- Responsive breakpoint at 768px

### Step 9: Additional styles (one at a time)
Each style uses `assemble_building()` helper and only defines what makes it unique.
Styles produce lists of cutouts and additions; shared helper manages CSG phases.

| Style | Massing | Key Implementation Notes |
|-------|---------|--------------------------|
| **Art Deco** | `stepped_mass` | Ziggurat setbacks, vertical fins (0.5mm+ thick FDM), geometric crown |
| **Classical** | `rect_mass` | Columns/pilasters via `column.py`, pediment (extruded triangle), symmetrical facade |
| **Skyscraper** | `podium_tower_mass` | Tall narrow form (stability: base_width >= 40% of height), curtain wall grid, crown |
| **Townhouse** | `rect_mass` (narrow) | Mansard roof, stoop (2-3 steps, 0.3mm/step), bay window, cornice with 45° chamfer |
| **Mediterranean** | `rect_mass` / `u_shape_mass` | Barrel roof (via `revolve_profile`), arched windows (resin) / rect (FDM), thick walls |
| **Tropical** | `rect_mass` / `l_shape_mass` | Deep overhangs with 45° support underneath, stilt base, multi-tier roof |
| **Victorian** | `l_shape_mass` | Asymmetric plan, turret (cylinder + cone cap), bay windows, complex roofline, HIGH detail — conditional feature gating for FDM |

For each style:
- Implement `generate()` using `assemble_building(shell, cutouts, additions)`
- Implement `validate_style_params()` for style-specific params
- Implement `style_params_schema()` returning JSON Schema
- Conditional feature gating by printer type:
  - FDM: disable arched windows, individual balusters, dormers, fine ornamental detail
  - Resin: enable all features
- Add parameterized test case to `test_styles.py` (auto-discovered via `list_styles()`)

**Style acceptance criteria** (each generated piece must):
1. Be recognizable as a hotel (entrance door, multiple floors with windows, signage-scale facade)
2. Have a visually distinct silhouette from every other style
3. Pass all 10 validation checks
4. Stand upright without tipping (stability: base footprint >= 40% of height for tall styles)
5. Be printable without supports on specified printer type

### Step 10: Polish & integration testing
- End-to-end test: start API, load UI, switch styles, download STL
- Parameterized style test across all 8 styles × both printer types
- Performance check: generation < 500ms simple styles, < 2s complex
- Triangle budget check: warn if > 50,000, error if > 200,000

---

## 3D Printing Constraints

Full printer profiles used by `PrinterProfile` in `config.py`. Values sourced from
`docs/3d-printing-constraints.md` Section 8.1.

```python
FDM_PROFILE = {
    # Minimum dimensions
    "min_wall_thickness": 0.8,       # mm (2 perimeters @ 0.4mm nozzle)
    "min_feature_size": 0.6,         # mm, smallest positive feature
    "min_hole_size": 0.6,            # mm, smallest cutout dimension
    "min_column_diameter": 0.8,      # mm, round columns
    "min_column_width": 0.6,         # mm, square columns
    "min_emboss_width": 0.5,         # mm
    "min_emboss_height": 0.2,        # mm
    "min_engrave_width": 0.4,        # mm
    "min_engrave_depth": 0.2,        # mm

    # Structural limits
    "max_overhang_angle": 45,        # degrees from vertical
    "max_bridge_span": 6.0,          # mm
    "max_aspect_ratio": 6,           # height:width for thin features

    # Base
    "base_thickness": 1.2,           # mm
    "base_chamfer": 0.3,             # mm, 45-degree

    # Cylinders
    "cylinder_segments_per_mm": 8,
    "min_cylinder_segments": 8,
    "max_cylinder_segments": 48,

    # Feature gating
    "use_window_frames": False,
    "use_individual_balusters": False,
    "use_arched_windows": False,
    "use_dormers": False,
}

RESIN_PROFILE = {
    "min_wall_thickness": 0.5,       # mm
    "min_feature_size": 0.2,         # mm
    "min_hole_size": 0.3,            # mm
    "min_column_diameter": 0.4,      # mm
    "min_column_width": 0.4,         # mm
    "min_emboss_width": 0.2,         # mm
    "min_emboss_height": 0.1,        # mm
    "min_engrave_width": 0.2,        # mm
    "min_engrave_depth": 0.1,        # mm

    "max_overhang_angle": 55,        # degrees from vertical
    "max_bridge_span": 999.0,        # mm (not a concern for resin)
    "max_aspect_ratio": 10,          # height:width

    "base_thickness": 1.0,           # mm
    "base_chamfer": 0.2,             # mm

    "cylinder_segments_per_mm": 12,
    "min_cylinder_segments": 12,
    "max_cylinder_segments": 64,

    "use_window_frames": True,
    "use_individual_balusters": True,
    "use_arched_windows": True,
    "use_dormers": True,
}
```

### Boolean Operation Constants

```python
BOOLEAN_OVERSHOOT = 0.1   # Extend subtractions past the target surface
BOOLEAN_EMBED = 0.1       # Embed additive features into the target surface
COPLANAR_OFFSET = 0.01    # Minimum offset to avoid coplanar faces
```

---

## Style Grammar Summary (8 styles)

| Style | Silhouette Cue | Key Features | Massing | Complexity |
|-------|---------------|--------------|---------|------------|
| Modern | Flat roof, horizontal bands | Grid windows, cantilever, penthouse | rect / L | Low |
| Skyscraper | Extreme slenderness | Curtain wall, podium, crown | podium+tower | Low-Med |
| Art Deco | Stepped ziggurat | Vertical fins, geometric crown | stepped | Medium |
| Classical | Triangular pediment | Columns, entablature, symmetry | rect | Medium |
| Mediterranean | Hip/barrel roof + deep eave | Arched windows, loggia | rect / U | Medium |
| Townhouse | Narrow tall rectangle | Mansard, stoop, bay window, cornice | rect (narrow) | Medium |
| Tropical | Massive overhang | Stilts, multi-tier roof | rect / L | Med-High |
| Victorian | Asymmetric multi-gable | Turret, bay windows, dormers | L | High |

---

## Key Design Decisions

1. **manifold3d over build123d/CadQuery** — 10x lighter dependency, guaranteed watertight output, faster booleans. Trade-off: no NURBS/fillets, but unnecessary at game-piece scale. Pin version with upper bound (`>=3.3.2, <4.0`).

2. **CSG three-phase assembly pattern** — Buildings are constructed in three phases (shell → subtract cutouts → add features) via a shared `assemble_building()` helper. All cutouts are batched into a single boolean. Styles define what to cut/add; the helper manages CSG operations. This prevents duplicating the pattern across 8 styles.

3. **Style as strategy pattern** — Each style is a class implementing `generate(params, profile) -> Manifold`. New styles added without modifying core code. Styles registered via decorator into `STYLE_REGISTRY`. Each style validates its own `style_params` via `validate_style_params()`.

4. **Base/pedestal on every piece** — Every generated piece gets a base slab (1.0-1.2mm thick with chamfer). Critical for: bed adhesion during FDM printing, stability during gameplay, and visual grounding.

5. **Conditional feature gating by printer type** — FDM profile disables features that won't print well (arched windows, individual balusters, dormers). Resin profile enables all features. Gated via `PrinterProfile` booleans, not per-style logic.

6. **FastAPI + three.js with no build step** — Lightweight server renders on demand; browser handles 3D preview. three.js loaded via import map from CDN. Frontend applies its own material + lighting (backend GLB has no materials). `GLTFLoader.parse()` for POST responses.

7. **Pydantic for all params** — Type-safe, JSON-serializable, auto-generates OpenAPI schema. `pydantic-settings` for server configuration from environment variables. Response models (`StyleInfo`, `ErrorResponse`) for consistent API responses.

8. **Sync endpoints for CPU-bound work** — Generation endpoints use `def` (not `async def`) so FastAPI delegates to thread pool. Prevents blocking the event loop during manifold3d operations.

9. **Tests alongside implementation** — Each step includes its corresponding tests. No deferred "write all tests at the end" step.

10. **`safe_scale()` wrapper** — The scalar `scale(float)` crashes Python bindings in manifold3d 3.3.2. All code uses the 3-vector form via `safe_scale()`. `set_circular_segments(16)` called at module init to prevent 4-segment circles on small radii.

11. **Empty manifold guards** — Empty manifolds propagate silently through all operations. Each CSG phase checks for empty results and raises `GeometryError` if detected.

12. **BuildResult dataclass** — `HotelBuilder.build()` returns `BuildResult` (manifold + metadata) not a raw `Manifold`. Metadata includes triangle count, bounding box, watertightness, warnings. API layer reads metadata for response headers.

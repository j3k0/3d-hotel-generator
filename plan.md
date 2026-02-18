# 3D Hotel Generator - Implementation Plan

## Project Goal
Build a Python tool that procedurally generates 3D-printable hotel game pieces (Monopoly-style, ~1-2cm tall) as STL files, with a web UI for previewing and customizing buildings.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Web UI (three.js)                  │
│   Parameter sliders → Preview GLB → Download STL    │
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
└─────────────────────────────────────────────────────┘
```

## Core Libraries

| Library | Purpose | Why |
|---------|---------|-----|
| **manifold3d** >=3.3 | CSG geometry engine | Guaranteed watertight output, fast booleans, lightweight |
| **trimesh** >=4.0 | Mesh I/O & validation | STL/GLB export, watertightness checks |
| **numpy** >=1.24 | Array ops | Required by both above |
| **fastapi** | Web API | Async, auto-docs, lightweight |
| **uvicorn** | ASGI server | Run FastAPI |
| **pydantic** | Config models | Param validation, serialization |

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
│       ├── geometry/
│       │   ├── __init__.py
│       │   ├── primitives.py      # Wrappers: box, cylinder, extrude
│       │   ├── booleans.py        # batch_union, batch_difference
│       │   └── transforms.py      # translate, rotate, mirror helpers
│       ├── components/
│       │   ├── __init__.py
│       │   ├── wall.py            # Wall with thickness
│       │   ├── window.py          # Window cutout + optional frame
│       │   ├── door.py            # Door cutout + canopy
│       │   ├── roof.py            # Flat, gabled, hipped, mansard, barrel-tile
│       │   ├── balcony.py         # Floor slab + railing
│       │   ├── column.py          # Round/square columns, pilasters
│       │   ├── floor_slab.py      # Per-floor horizontal slab
│       │   └── facade.py          # Compose windows/doors onto a wall
│       ├── styles/
│       │   ├── __init__.py
│       │   ├── base.py            # Abstract style + style registry
│       │   ├── modern.py          # Flat roof, grid windows, clean lines
│       │   ├── classical.py       # Columns, pediment, symmetry
│       │   ├── art_deco.py        # Stepped massing, vertical fins
│       │   ├── victorian.py       # Turrets, bay windows, complex roof
│       │   ├── mediterranean.py   # Barrel tile, arches, thick walls
│       │   ├── tropical.py        # Deep overhangs, stilts, thatch
│       │   ├── skyscraper.py      # Tall/narrow, curtain wall, crown
│       │   └── townhouse.py       # Narrow lot, mansard, stoop
│       ├── assembly/
│       │   ├── __init__.py
│       │   └── building.py        # Assemble components via CSG tree
│       ├── export/
│       │   ├── __init__.py
│       │   ├── stl.py             # Binary STL via trimesh
│       │   └── glb.py             # GLB for web preview
│       ├── validation/
│       │   ├── __init__.py
│       │   └── checks.py          # Watertight, min thickness, dimensions
│       ├── config.py              # Pydantic models for all parameters
│       └── api.py                 # FastAPI endpoints
├── web/
│   ├── index.html                 # Single-page app
│   ├── app.js                     # three.js viewer + parameter UI
│   └── style.css
└── tests/
    ├── test_geometry.py
    ├── test_components.py
    ├── test_styles.py
    ├── test_assembly.py
    └── test_export.py
```

---

## Implementation Steps (in order)

### Step 1: Project scaffolding
- Create `pyproject.toml` with dependencies and project metadata
- Create package structure (`src/hotel_generator/` with `__init__.py` files)
- Create `.gitignore`

### Step 2: Geometry primitives layer
- `geometry/primitives.py` - Thin wrappers around manifold3d: `box()`, `cylinder()`, `extrude_polygon()`
- `geometry/booleans.py` - `union_all()`, `difference_all()` using `Manifold.batch_boolean()`
- `geometry/transforms.py` - `translate()`, `rotate_z()`, `mirror_x()` helpers
- Key rule: all cutouts overshoot by 0.1mm to avoid coplanar faces

### Step 3: Building components
- `components/wall.py` - Solid box with parametric width/height/thickness
- `components/window.py` - Cutout solid + optional frame + optional sill
- `components/door.py` - Cutout solid + optional canopy
- `components/roof.py` - Generators for: flat (with parapet), gabled, hipped, mansard, barrel-tile
- `components/balcony.py` - Floor slab + simple railing posts
- `components/column.py` - Round cylinder or square pilaster
- `components/floor_slab.py` - Horizontal divider with optional groove
- `components/facade.py` - Place windows/doors on a wall at specified positions

### Step 4: Style system
- `styles/base.py` - `HotelStyle` abstract base with `generate(params) -> Manifold`
- `config.py` - Pydantic models: `BuildingParams` (dimensions, floors, style name), per-style params
- `styles/modern.py` - First style: flat roof, grid windows, optional cantilever, penthouse box
- Each style defines: floor plan shape, stacking rules, window pattern, roof type, decorations

### Step 5: Assembly engine
- `assembly/building.py` - `HotelBuilder.build(params) -> Manifold`
  1. Build solid shell from floor plan + height
  2. Batch all window/door cutouts into single union, then one difference
  3. Batch all additive features (roof, balconies, frames), then one union
  4. Return final manifold

### Step 6: Export pipeline
- `export/stl.py` - Convert Manifold → trimesh.Trimesh → binary STL
- `export/glb.py` - Convert Manifold → trimesh.Trimesh → GLB (for three.js)
- `validation/checks.py` - Verify watertight, volume > 0, bounding box within limits

### Step 7: API server
- `api.py` - FastAPI app with endpoints:
  - `POST /generate` - Accept BuildingParams JSON, return GLB preview
  - `POST /export/stl` - Accept BuildingParams JSON, return STL file download
  - `GET /styles` - List available styles and their parameter schemas
  - `GET /health` - Health check

### Step 8: Web UI
- `web/index.html` - Single page with three.js viewport + controls sidebar
- `web/app.js`:
  - Style selector dropdown
  - Parameter sliders (dynamically generated from `/styles` response)
  - three.js GLTFLoader for preview
  - Orbit controls for rotation/zoom
  - "Download STL" button
- `web/style.css` - Clean minimal styling
- FastAPI serves static files from `web/`

### Step 9: Additional styles (one at a time)
- `styles/art_deco.py` - Stepped ziggurat massing, vertical fins, geometric crown
- `styles/classical.py` - Columns/pilasters, pediment, symmetrical facade
- `styles/skyscraper.py` - Tall narrow form, curtain wall grid, crown element
- `styles/townhouse.py` - Narrow lot, mansard roof, stoop entry
- `styles/mediterranean.py` - Barrel tile roof, arched windows, thick walls
- `styles/tropical.py` - Deep overhangs, stilt base, multi-tier roof
- `styles/victorian.py` - Asymmetric plan, turret, bay windows, complex roofline

### Step 10: Tests
- `test_geometry.py` - Primitives produce valid manifolds
- `test_components.py` - Each component is watertight
- `test_styles.py` - Each style generates a valid building
- `test_assembly.py` - Full assembly pipeline produces watertight mesh
- `test_export.py` - STL/GLB export produces valid files

---

## 3D Printing Constraints (baked into component generators)

| Constraint | FDM Value | Resin Value |
|---|---|---|
| Min wall thickness | 0.8mm | 0.3mm |
| Min feature size | 0.6mm | 0.2mm |
| Min column diameter | 0.8mm | 0.4mm |
| Min embossed detail | 0.3mm | 0.15mm |
| Max unsupported overhang | 45 deg | 60 deg |
| Boolean cutout overshoot | 0.1mm | 0.1mm |

Components will have a `printer_type` parameter ("fdm" | "resin") that adjusts minimum dimensions.

---

## Style Grammar Summary (8 styles)

| Style | Silhouette Cue | Key Features | Complexity |
|---|---|---|---|
| Modern | Flat roof, horizontal | Grid windows, cantilever, penthouse | Low |
| Skyscraper | Extreme slenderness | Curtain wall, podium, crown | Low-Med |
| Art Deco | Stepped ziggurat | Vertical fins, geometric crown | Medium |
| Classical | Triangular pediment | Columns, entablature, symmetry | Medium |
| Mediterranean | Hip roof + deep eave | Arched windows, barrel tile, loggia | Medium |
| Townhouse | Narrow tall rectangle | Mansard, stoop, bay window, cornice | Medium |
| Tropical | Massive overhang | Stilts, thatch texture, multi-tier roof | Med-High |
| Victorian | Asymmetric multi-gable | Turret, bay windows, dormers | High |

---

## Key Design Decisions

1. **manifold3d over build123d/CadQuery** - 10x lighter dependency, guaranteed watertight output, faster booleans. Trade-off: no NURBS/fillets, but unnecessary at game-piece scale.

2. **CSG tree approach** - Buildings are constructed as union/difference operations on primitives. All cutouts are batched into a single boolean for performance.

3. **Style as strategy pattern** - Each style is a class implementing `generate(params) -> Manifold`. New styles can be added without modifying core code.

4. **FastAPI + three.js** - Lightweight server renders on demand; browser handles 3D preview with orbit controls. No heavy 3D framework needed.

5. **Pydantic for all params** - Type-safe, JSON-serializable, auto-generates OpenAPI schema for the web UI to consume.

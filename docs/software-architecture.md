# Software Architecture Report: 3D Hotel Generator

## Overview

This document describes the software architecture for a Python tool that procedurally generates 3D-printable miniature hotel game pieces as STL files, with a FastAPI backend and three.js web UI. The core geometry engine is manifold3d (CSG booleans, guaranteed watertight output), with trimesh handling mesh I/O. The system exposes a REST API that accepts building parameters, runs them through a style-driven generation pipeline, and returns GLB previews or STL downloads.

The architecture prioritizes:
- **Correctness**: every generated mesh must be watertight and printable.
- **Extensibility**: new hotel styles plug in without touching core code.
- **Testability**: geometry logic, components, styles, and the full pipeline are all independently testable.
- **Simplicity**: this is a focused tool, not a framework. Avoid abstraction until repetition demands it.

---

## 1. Project Structure and Module Organization

```
src/hotel_generator/
    __init__.py              # Package version, convenience re-exports
    config.py                # All Pydantic models (params, constraints, responses)
    api.py                   # FastAPI app, endpoints, middleware

    geometry/
        __init__.py          # Re-export primitives, booleans, transforms
        primitives.py        # box(), cylinder(), extrude_polygon()
        booleans.py          # union_all(), difference_all()
        transforms.py        # translate(), rotate_z(), mirror_x()

    components/
        __init__.py          # Re-export component functions
        wall.py              # solid_wall(width, height, thickness) -> Manifold
        window.py            # window_cutout(...), window_frame(...)
        door.py              # door_cutout(...), door_canopy(...)
        roof.py              # flat_roof(), gabled_roof(), hipped_roof(), etc.
        balcony.py           # balcony_slab(...), railing(...)
        column.py            # round_column(), square_pilaster()
        floor_slab.py        # floor_slab(width, depth, thickness)
        facade.py            # place_openings(wall, openings) -> Manifold

    styles/
        __init__.py          # Style registry, get_style(), list_styles()
        base.py              # HotelStyle ABC
        modern.py            # ModernStyle(HotelStyle)
        classical.py         # ClassicalStyle(HotelStyle)
        art_deco.py          # ArtDecoStyle(HotelStyle)
        victorian.py         # VictorianStyle(HotelStyle)
        mediterranean.py     # MediterraneanStyle(HotelStyle)
        tropical.py          # TropicalStyle(HotelStyle)
        skyscraper.py        # SkyscraperStyle(HotelStyle)
        townhouse.py         # TownhouseStyle(HotelStyle)

    assembly/
        __init__.py
        building.py          # HotelBuilder: params -> Manifold

    export/
        __init__.py
        stl.py               # manifold_to_stl(manifold) -> bytes
        glb.py               # manifold_to_glb(manifold) -> bytes

    validation/
        __init__.py
        checks.py            # is_watertight(), check_min_thickness(), check_bounds()
```

### Design Principles

**Flat within each subpackage.** Each subpackage has one responsibility (geometry math, building components, architectural styles, etc.). Files within a subpackage are individual modules, not nested further. There is no `geometry/csg/advanced/` -- just `geometry/booleans.py`.

**Functions over classes for stateless operations.** The geometry and component layers are pure functions: they take parameters, return a `Manifold`. No mutable state, no `self`. This makes them trivially testable and composable.

**Classes where identity matters.** Styles are classes (they implement an interface). The builder is a class (it holds an intermediate state during assembly). The API app is a class (FastAPI instance). Everything else is functions.

**`__init__.py` as a public API.** Each subpackage's `__init__.py` re-exports the symbols that other layers should use. Internal helpers stay private (prefixed with `_` or simply not exported).

```python
# src/hotel_generator/geometry/__init__.py
from hotel_generator.geometry.primitives import box, cylinder, extrude_polygon
from hotel_generator.geometry.booleans import union_all, difference_all
from hotel_generator.geometry.transforms import translate, rotate_z, mirror_x

__all__ = [
    "box", "cylinder", "extrude_polygon",
    "union_all", "difference_all",
    "translate", "rotate_z", "mirror_x",
]
```

This lets consuming code write `from hotel_generator.geometry import box, union_all` without knowing the internal file layout. If we later merge `primitives.py` and `transforms.py`, imports don't break.

---

## 2. Strategy Pattern for Styles

### Abstract Base Class

Each architectural style encapsulates the full decision-making for how a hotel of that style looks: floor plan shape, window placement pattern, roof type, decorative elements, and how floors stack. The `HotelStyle` ABC defines this contract.

```python
# src/hotel_generator/styles/base.py
from abc import ABC, abstractmethod
from manifold3d import Manifold
from hotel_generator.config import BuildingParams, PrinterConstraints


class HotelStyle(ABC):
    """Base class for all hotel architectural styles."""

    # Subclasses set these as class attributes
    name: str                    # e.g. "modern"
    display_name: str            # e.g. "Modern"
    description: str             # one-line summary for the UI

    @abstractmethod
    def generate(
        self,
        params: BuildingParams,
        constraints: PrinterConstraints,
    ) -> Manifold:
        """Generate the complete hotel geometry.

        Args:
            params: Building dimensions, floor count, style-specific overrides.
            constraints: Min wall thickness, min feature size, etc.

        Returns:
            A single watertight Manifold ready for export.

        Raises:
            GeometryError: If boolean operations fail or produce degenerate geometry.
        """
        ...

    @classmethod
    def style_params_schema(cls) -> dict:
        """Return JSON Schema for this style's specific parameters.

        The base implementation returns an empty schema. Styles with
        additional parameters (e.g., ArtDeco's step_count) override this.
        """
        return {}
```

A style implementation looks like this:

```python
# src/hotel_generator/styles/modern.py
from manifold3d import Manifold
from hotel_generator.styles.base import HotelStyle
from hotel_generator.config import BuildingParams, PrinterConstraints
from hotel_generator.geometry import box, union_all, difference_all, translate
from hotel_generator.components import (
    solid_wall, window_cutout, flat_roof, floor_slab, facade
)


class ModernStyle(HotelStyle):
    name = "modern"
    display_name = "Modern"
    description = "Flat roof, grid windows, clean horizontal lines"

    def generate(
        self,
        params: BuildingParams,
        constraints: PrinterConstraints,
    ) -> Manifold:
        w, d, h = params.width, params.depth, params.total_height
        wall_t = max(constraints.min_wall_thickness, params.wall_thickness)

        # 1. Solid shell
        shell = box(w, d, h)

        # 2. Window grid cutouts
        cutouts = []
        for floor_i in range(params.floors):
            y_offset = floor_i * params.floor_height + params.floor_height * 0.35
            for col in range(params.windows_per_floor):
                x_offset = _window_x(col, params.windows_per_floor, w)
                cutouts.append(translate(
                    window_cutout(
                        params.window_width,
                        params.window_height,
                        wall_t,
                    ),
                    x=x_offset, y=0, z=y_offset,
                ))
        if cutouts:
            shell = shell - union_all(cutouts)

        # 3. Additive features
        additions = [flat_roof(w, d, wall_t)]
        for floor_i in range(1, params.floors):
            additions.append(translate(
                floor_slab(w, d, constraints.min_feature_size),
                z=floor_i * params.floor_height,
            ))
        result = shell + union_all(additions)

        return result

    @classmethod
    def style_params_schema(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "cantilever_depth": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Depth of upper-floor cantilever overhang (mm)",
                },
                "penthouse": {
                    "type": "boolean",
                    "default": False,
                    "description": "Add a setback penthouse floor",
                },
            },
        }
```

### Style Registry

Styles self-register via a simple module-level registry. No metaclass magic, no decorators with hidden side effects -- just an explicit dict and explicit registration.

```python
# src/hotel_generator/styles/__init__.py
from hotel_generator.styles.base import HotelStyle

_registry: dict[str, type[HotelStyle]] = {}


def register_style(cls: type[HotelStyle]) -> type[HotelStyle]:
    """Register a style class. Use as a decorator on the class."""
    if not isinstance(cls.name, str) or not cls.name:
        raise ValueError(f"{cls.__name__} must define a non-empty 'name' attribute")
    if cls.name in _registry:
        raise ValueError(f"Duplicate style name: {cls.name!r}")
    _registry[cls.name] = cls
    return cls


def get_style(name: str) -> HotelStyle:
    """Instantiate a style by name. Raises KeyError if unknown."""
    if name not in _registry:
        available = ", ".join(sorted(_registry.keys()))
        raise KeyError(f"Unknown style {name!r}. Available: {available}")
    return _registry[name]()


def list_styles() -> list[dict]:
    """Return metadata for all registered styles (for the API)."""
    return [
        {
            "name": cls.name,
            "display_name": cls.display_name,
            "description": cls.description,
            "params_schema": cls.style_params_schema(),
        }
        for cls in _registry.values()
    ]


# --- Eagerly import all style modules so they register themselves ---
from hotel_generator.styles.modern import ModernStyle        # noqa: E402, F401
from hotel_generator.styles.classical import ClassicalStyle  # noqa: E402, F401
from hotel_generator.styles.art_deco import ArtDecoStyle     # noqa: E402, F401
# ... etc for all style modules
```

And each style module uses the decorator:

```python
# src/hotel_generator/styles/modern.py
from hotel_generator.styles import register_style
from hotel_generator.styles.base import HotelStyle

@register_style
class ModernStyle(HotelStyle):
    name = "modern"
    # ...
```

**Why this approach over `importlib` scanning or `__init_subclass__`:**
- Explicit imports in `__init__.py` make it obvious which styles exist. No hidden filesystem scanning.
- The `register_style` decorator is a single line; if a developer forgets it, the style simply won't appear (safe failure).
- `__init_subclass__` would auto-register every subclass including test doubles -- we don't want that.

---

## 3. Builder Pattern for Assembly

The assembly layer orchestrates the full generation pipeline: take `BuildingParams`, invoke the right style, validate the result, and return the mesh. This is the single entry point that the API calls.

```python
# src/hotel_generator/assembly/building.py
from dataclasses import dataclass, field
from manifold3d import Manifold
from hotel_generator.config import BuildingParams, PrinterConstraints, PrinterType
from hotel_generator.styles import get_style
from hotel_generator.validation.checks import validate_mesh


# Default constraints per printer type
_DEFAULT_CONSTRAINTS = {
    PrinterType.FDM: PrinterConstraints(
        min_wall_thickness=0.8,
        min_feature_size=0.6,
        min_column_diameter=0.8,
        min_emboss_depth=0.3,
        max_overhang_angle=45.0,
        cutout_overshoot=0.1,
    ),
    PrinterType.RESIN: PrinterConstraints(
        min_wall_thickness=0.3,
        min_feature_size=0.2,
        min_column_diameter=0.4,
        min_emboss_depth=0.15,
        max_overhang_angle=60.0,
        cutout_overshoot=0.1,
    ),
}


@dataclass
class BuildResult:
    """Output of the build pipeline."""
    manifold: Manifold
    triangle_count: int
    bounding_box: tuple[tuple[float, float, float], tuple[float, float, float]]
    is_watertight: bool
    warnings: list[str] = field(default_factory=list)


class HotelBuilder:
    """Assembles a hotel building from parameters.

    This is the main entry point for generation. It:
    1. Resolves printer constraints from the printer type.
    2. Looks up the style by name.
    3. Delegates geometry generation to the style.
    4. Validates the result.
    5. Returns a BuildResult with the mesh and metadata.
    """

    def __init__(
        self,
        constraints_override: dict[PrinterType, PrinterConstraints] | None = None,
    ):
        self._constraints = {**_DEFAULT_CONSTRAINTS}
        if constraints_override:
            self._constraints.update(constraints_override)

    def build(self, params: BuildingParams) -> BuildResult:
        """Run the full generation pipeline.

        Args:
            params: All building parameters including style name.

        Returns:
            BuildResult with the generated manifold and validation metadata.

        Raises:
            KeyError: If the style name is not registered.
            GeometryError: If geometry generation fails.
            ValidationError: If the result fails printability checks.
        """
        constraints = self._constraints[params.printer_type]

        # 1. Resolve style
        style = get_style(params.style)

        # 2. Generate geometry
        manifold = style.generate(params, constraints)

        # 3. Validate
        warnings = validate_mesh(manifold, constraints)

        # 4. Package result
        mesh = manifold.to_mesh()
        bbox_min = tuple(mesh.vert_properties.min(axis=0)[:3])
        bbox_max = tuple(mesh.vert_properties.max(axis=0)[:3])

        return BuildResult(
            manifold=manifold,
            triangle_count=mesh.tri_verts.shape[0],
            bounding_box=(bbox_min, bbox_max),
            is_watertight=True,  # manifold3d guarantees this
            warnings=warnings,
        )
```

### Why a Class Instead of a Function

The builder is a class because it holds configuration state (printer constraint profiles) that persists across multiple builds. The API creates one `HotelBuilder` at startup and reuses it. In tests, you create one with custom constraints.

However, the `build()` method itself is essentially a pipeline function. There is no intermediate mutable "building-in-progress" state exposed to callers. The style's `generate()` method handles the internal CSG tree construction.

### Internal Assembly Flow Within a Style

Inside each style's `generate()`, the actual CSG assembly follows a consistent three-phase pattern:

```
Phase 1: Subtractive body
    shell = box(width, depth, height)
    cutouts = [window_cutout(...), door_cutout(...), ...]
    body = shell - union_all(cutouts)

Phase 2: Additive features
    additions = [roof, floor_slabs, balconies, frames, columns, ...]
    result = body + union_all(additions)

Phase 3: Final cleanup (optional)
    result = result - union_all(cleanup_cuts)   # e.g., base flatten
```

Batching all subtractive ops into a single `union_all` then one difference -- and likewise for additive ops -- minimizes the number of CSG boolean evaluations. This is a performance-critical pattern: N individual boolean operations are far slower than one batched operation.

---

## 4. Pydantic Models for Configuration

### Core Models

```python
# src/hotel_generator/config.py
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from typing import Any


class PrinterType(str, Enum):
    FDM = "fdm"
    RESIN = "resin"


class PrinterConstraints(BaseModel):
    """Hardware limits for a given printer type.

    These are not user-facing parameters -- they are system constants
    looked up by printer_type. Exposed here for testability and
    configuration override.
    """
    min_wall_thickness: float = Field(ge=0.1, le=5.0, description="mm")
    min_feature_size: float = Field(ge=0.1, le=5.0, description="mm")
    min_column_diameter: float = Field(ge=0.1, le=5.0, description="mm")
    min_emboss_depth: float = Field(ge=0.05, le=2.0, description="mm")
    max_overhang_angle: float = Field(ge=0, le=90, description="degrees")
    cutout_overshoot: float = Field(default=0.1, ge=0.01, le=1.0, description="mm")


class BuildingParams(BaseModel):
    """User-facing parameters for generating a hotel building.

    Dimensions are in millimeters. The generated piece is designed
    to be roughly 10-20mm tall for game-piece scale.
    """

    # Style selection
    style: str = Field(
        default="modern",
        description="Architectural style name (e.g. 'modern', 'art_deco')",
    )

    # Overall dimensions (mm)
    width: float = Field(default=12.0, ge=5.0, le=40.0, description="Building width in mm")
    depth: float = Field(default=10.0, ge=5.0, le=40.0, description="Building depth in mm")
    floors: int = Field(default=3, ge=1, le=12, description="Number of floors")
    floor_height: float = Field(default=3.0, ge=1.5, le=8.0, description="Per-floor height in mm")

    # Wall
    wall_thickness: float = Field(default=1.0, ge=0.3, le=3.0, description="Exterior wall thickness in mm")

    # Windows
    windows_per_floor: int = Field(default=3, ge=0, le=10)
    window_width: float = Field(default=1.5, ge=0.3, le=5.0, description="mm")
    window_height: float = Field(default=2.0, ge=0.3, le=5.0, description="mm")

    # Printer
    printer_type: PrinterType = Field(default=PrinterType.FDM)

    # Style-specific overrides (validated by the style, not here)
    style_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Style-specific parameters (see /styles endpoint for schema)",
    )

    @property
    def total_height(self) -> float:
        return self.floors * self.floor_height

    @model_validator(mode="after")
    def check_proportions(self) -> "BuildingParams":
        """Warn about extreme aspect ratios that won't print well."""
        h = self.total_height
        min_base = min(self.width, self.depth)
        if min_base > 0 and h / min_base > 8:
            raise ValueError(
                f"Aspect ratio {h/min_base:.1f}:1 is too tall for stable printing. "
                f"Max recommended is 8:1."
            )
        return self

    @model_validator(mode="after")
    def check_window_fits(self) -> "BuildingParams":
        """Ensure windows actually fit on the wall."""
        if self.windows_per_floor == 0:
            return self
        total_window_width = self.windows_per_floor * self.window_width
        available = self.width - 2 * self.wall_thickness
        if total_window_width > available:
            raise ValueError(
                f"Windows ({self.windows_per_floor} x {self.window_width}mm = "
                f"{total_window_width}mm) don't fit in wall width "
                f"({available:.1f}mm available)"
            )
        if self.window_height > self.floor_height * 0.8:
            raise ValueError(
                f"Window height {self.window_height}mm exceeds 80% of "
                f"floor height {self.floor_height}mm"
            )
        return self
```

### API Response Models

```python
# Also in config.py

class StyleInfo(BaseModel):
    """Metadata about an available style, returned by GET /styles."""
    name: str
    display_name: str
    description: str
    params_schema: dict = Field(
        default_factory=dict,
        description="JSON Schema for style-specific parameters",
    )


class GenerateResponse(BaseModel):
    """Metadata returned alongside the GLB binary from POST /generate."""
    triangle_count: int
    bounding_box_mm: tuple[tuple[float, float, float], tuple[float, float, float]]
    warnings: list[str] = []


class ErrorResponse(BaseModel):
    """Standard error response body."""
    error: str
    detail: str | None = None
    field: str | None = None
```

### Design Rationale

**`style_params` is a loose `dict[str, Any]`.** We deliberately do not try to validate style-specific parameters in the shared `BuildingParams` model. Each style knows its own parameters and validates them inside `generate()`. This avoids a combinatorial explosion of union-typed config models and keeps the core model stable as new styles are added.

**Constraints are not user-facing.** Users pick `printer_type: "fdm"` or `"resin"`. The system internally resolves this to a `PrinterConstraints` object. This keeps the user-facing API surface small.

**Validation is proactive, not defensive.** The `model_validator` methods catch impossible configurations early -- before we spend time on geometry. Error messages explain *why* the configuration is wrong and what the limits are.

---

## 5. FastAPI Endpoint Design

```python
# src/hotel_generator/api.py
import hashlib
import json
from fastapi import FastAPI, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from hotel_generator.config import BuildingParams, StyleInfo, GenerateResponse, ErrorResponse
from hotel_generator.assembly.building import HotelBuilder
from hotel_generator.export.glb import manifold_to_glb
from hotel_generator.export.stl import manifold_to_stl
from hotel_generator.styles import list_styles

app = FastAPI(
    title="3D Hotel Generator",
    version="0.1.0",
    description="Generate 3D-printable miniature hotel game pieces",
)

builder = HotelBuilder()


@app.get(
    "/styles",
    response_model=list[StyleInfo],
    summary="List available architectural styles",
)
async def get_styles():
    """Return all registered styles with their display names,
    descriptions, and parameter schemas."""
    return list_styles()


@app.post(
    "/generate",
    summary="Generate GLB preview",
    responses={
        200: {
            "content": {"model/gltf-binary": {}},
            "description": "GLB binary with metadata in X-Metadata header",
        },
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def generate_preview(params: BuildingParams):
    """Generate a hotel building and return a GLB file for 3D preview.

    Building metadata (triangle count, bounding box, warnings) is
    returned in the X-Build-Metadata response header as JSON.
    """
    result = builder.build(params)
    glb_bytes = manifold_to_glb(result.manifold)

    metadata = GenerateResponse(
        triangle_count=result.triangle_count,
        bounding_box_mm=result.bounding_box,
        warnings=result.warnings,
    )

    return Response(
        content=glb_bytes,
        media_type="model/gltf-binary",
        headers={
            "X-Build-Metadata": metadata.model_dump_json(),
            "Content-Disposition": 'inline; filename="hotel_preview.glb"',
        },
    )


@app.post(
    "/export/stl",
    summary="Export STL for 3D printing",
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "Binary STL file",
        },
        400: {"model": ErrorResponse},
    },
)
async def export_stl(params: BuildingParams):
    """Generate a hotel building and return a binary STL file download."""
    result = builder.build(params)
    stl_bytes = manifold_to_stl(result.manifold)

    filename = f"hotel_{params.style}_{params.floors}f.stl"
    return Response(
        content=stl_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve the web UI
app.mount("/", StaticFiles(directory="web", html=True), name="web")
```

### Endpoint Summary

| Method | Path | Request | Response | Purpose |
|--------|------|---------|----------|---------|
| `GET` | `/styles` | -- | `list[StyleInfo]` JSON | UI populates style dropdown and generates parameter sliders |
| `POST` | `/generate` | `BuildingParams` JSON | GLB binary + metadata header | Browser loads into three.js for real-time preview |
| `POST` | `/export/stl` | `BuildingParams` JSON | Binary STL file download | User saves for slicing/printing |
| `GET` | `/health` | -- | `{"status": "ok"}` | Health check |

### Why POST for generate/export

Both `/generate` and `/export/stl` use POST because the request body (`BuildingParams`) can be large and complex, especially with `style_params`. GET with query parameters would be awkward for nested JSON. POST also avoids URL-length limits and makes it clear these are "compute something" operations.

### Metadata in Headers vs. Multipart

Build metadata (triangle count, bounding box, warnings) rides in the `X-Build-Metadata` response header rather than being a multipart response. This is simpler for the client: fetch the GLB, read one header, done. The alternative -- wrapping GLB in a JSON envelope with base64 -- would double the response size and add decode overhead.

---

## 6. Error Handling Strategy

### What Can Go Wrong

| Failure Mode | Cause | Frequency | Impact |
|---|---|---|---|
| **Invalid parameters** | User sends out-of-range values | Common | 400, no compute wasted |
| **Unknown style** | Typo in style name | Common | 400, fast failure |
| **Windows don't fit** | Too many/large windows for wall width | Common | 400, caught by Pydantic validator |
| **Extreme aspect ratio** | Very tall, very narrow building | Occasional | 400, caught by Pydantic validator |
| **CSG boolean failure** | Degenerate geometry (zero-area faces, etc.) | Rare | 500, need graceful fallback |
| **Manifold not watertight** | Shouldn't happen with manifold3d, but... | Very rare | 500, log and report |
| **Memory exhaustion** | Extremely high polygon count | Very rare | 500, OOM |
| **Style-specific param error** | Invalid value in `style_params` | Occasional | 400, style validates |

### Error Hierarchy

```python
# src/hotel_generator/errors.py

class HotelGeneratorError(Exception):
    """Base exception for all hotel generator errors."""
    pass


class InvalidParamsError(HotelGeneratorError):
    """User-supplied parameters are invalid. Maps to HTTP 400."""
    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


class GeometryError(HotelGeneratorError):
    """Geometry operation failed (CSG failure, degenerate mesh).
    Maps to HTTP 500."""
    pass


class ValidationError(HotelGeneratorError):
    """Generated mesh failed printability validation.
    Maps to HTTP 422 (produced output, but it's not usable)."""
    pass
```

### FastAPI Exception Handlers

```python
# In api.py

from hotel_generator.errors import (
    HotelGeneratorError, InvalidParamsError, GeometryError, ValidationError,
)

@app.exception_handler(InvalidParamsError)
async def handle_invalid_params(request, exc: InvalidParamsError):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "field": exc.field},
    )

@app.exception_handler(GeometryError)
async def handle_geometry_error(request, exc: GeometryError):
    # Log the full traceback for debugging
    logger.exception("Geometry operation failed")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Geometry generation failed",
            "detail": str(exc),
        },
    )

@app.exception_handler(ValidationError)
async def handle_validation_error(request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Generated mesh failed validation", "detail": str(exc)},
    )
```

### Defensive Geometry Practices

Within styles and components, use these patterns to prevent CSG failures:

```python
# ALWAYS overshoot cutouts to avoid coplanar faces
def window_cutout(width: float, height: float, wall_thickness: float) -> Manifold:
    """Create a window cutout that overshoots the wall by 0.1mm on both sides."""
    return box(
        width,
        wall_thickness + 0.2,  # overshoot both sides
        height,
    )

# NEVER union zero-volume manifolds
def union_all(manifolds: list[Manifold]) -> Manifold:
    """Union a list of manifolds, filtering out empties."""
    valid = [m for m in manifolds if m.num_tri() > 0]
    if not valid:
        raise GeometryError("union_all called with no valid manifolds")
    if len(valid) == 1:
        return valid[0]
    return Manifold.batch_boolean(valid, OpType.Add)
```

---

## 7. Testing Strategy

### Test Organization

```
tests/
    conftest.py              # Shared fixtures (sample params, printer constraints)
    test_geometry.py         # Unit: primitives, booleans, transforms
    test_components.py       # Unit: each component function
    test_styles.py           # Integration: each style generates valid output
    test_assembly.py         # Integration: full pipeline from params to mesh
    test_export.py           # Integration: STL/GLB export produces valid files
    test_config.py           # Unit: Pydantic validation logic
    test_api.py              # Integration: FastAPI endpoint tests
```

### Fixtures

```python
# tests/conftest.py
import pytest
from hotel_generator.config import BuildingParams, PrinterConstraints, PrinterType
from hotel_generator.assembly.building import HotelBuilder


@pytest.fixture
def fdm_constraints() -> PrinterConstraints:
    return PrinterConstraints(
        min_wall_thickness=0.8,
        min_feature_size=0.6,
        min_column_diameter=0.8,
        min_emboss_depth=0.3,
        max_overhang_angle=45.0,
        cutout_overshoot=0.1,
    )


@pytest.fixture
def default_params() -> BuildingParams:
    return BuildingParams(
        style="modern",
        width=12.0,
        depth=10.0,
        floors=3,
        floor_height=3.0,
        wall_thickness=1.0,
        windows_per_floor=3,
        printer_type=PrinterType.FDM,
    )


@pytest.fixture
def builder() -> HotelBuilder:
    return HotelBuilder()
```

### Geometry Unit Tests

Every primitive and boolean operation must produce valid manifolds: positive volume, correct triangle count properties, and expected bounding boxes.

```python
# tests/test_geometry.py
from hotel_generator.geometry import box, cylinder, union_all, translate
import pytest


class TestBox:
    def test_basic_box(self):
        b = box(10, 10, 10)
        assert b.num_tri() == 12  # cube = 6 faces * 2 triangles
        assert b.volume() == pytest.approx(1000.0, rel=1e-3)

    def test_thin_box_above_minimum(self):
        """A 0.8mm wall should still produce valid geometry."""
        b = box(10, 0.8, 10)
        assert b.volume() > 0
        assert b.num_tri() > 0

    def test_zero_dimension_raises(self):
        """Zero-width geometry should fail explicitly."""
        with pytest.raises(Exception):
            box(0, 10, 10)


class TestBooleans:
    def test_union_preserves_watertight(self):
        a = box(10, 10, 10)
        b = translate(box(5, 5, 5), x=7)
        result = union_all([a, b])
        assert result.volume() > 0
        # manifold3d guarantees watertight, but verify non-degenerate
        assert result.num_tri() > 12

    def test_difference_creates_cavity(self):
        outer = box(10, 10, 10)
        inner = translate(box(6, 6, 6), x=2, y=2, z=2)
        result = outer - inner
        assert result.volume() < outer.volume()
        assert result.volume() > 0
```

### Component Tests

Each component is tested in isolation: does it produce geometry of approximately the right size and shape?

```python
# tests/test_components.py
from hotel_generator.components.wall import solid_wall
from hotel_generator.components.roof import flat_roof, gabled_roof
import pytest


class TestWall:
    def test_wall_dimensions(self):
        w = solid_wall(width=10, height=9, thickness=1.0)
        assert w.volume() == pytest.approx(10 * 9 * 1.0, rel=0.01)

    def test_wall_min_thickness(self):
        w = solid_wall(width=10, height=9, thickness=0.3)
        assert w.volume() > 0


class TestRoof:
    def test_flat_roof_covers_building(self):
        r = flat_roof(width=12, depth=10, parapet_height=0.5)
        bbox = _bounding_box(r)
        assert bbox.x_size >= 12
        assert bbox.y_size >= 10

    def test_gabled_roof_taller_than_flat(self):
        flat = flat_roof(width=12, depth=10, parapet_height=0.5)
        gabled = gabled_roof(width=12, depth=10, pitch_angle=30)
        assert _bounding_box(gabled).z_size > _bounding_box(flat).z_size
```

### Style Integration Tests

Every registered style must produce a valid, non-degenerate building for default parameters. This is a smoke test that catches broken style implementations.

```python
# tests/test_styles.py
import pytest
from hotel_generator.styles import list_styles, get_style
from hotel_generator.config import BuildingParams, PrinterConstraints, PrinterType


@pytest.fixture(params=[s["name"] for s in list_styles()])
def style_name(request):
    return request.param


class TestAllStyles:
    def test_generates_valid_mesh(self, style_name, default_params, fdm_constraints):
        """Every style must produce a valid manifold with default params."""
        default_params.style = style_name
        style = get_style(style_name)
        result = style.generate(default_params, fdm_constraints)
        assert result.num_tri() > 0
        assert result.volume() > 0

    def test_has_metadata(self, style_name):
        style = get_style(style_name)
        assert style.name == style_name
        assert len(style.display_name) > 0
        assert len(style.description) > 0
```

### Full Pipeline Integration Tests

```python
# tests/test_assembly.py
from hotel_generator.assembly.building import HotelBuilder
from hotel_generator.config import BuildingParams, PrinterType
from hotel_generator.export.stl import manifold_to_stl
from hotel_generator.export.glb import manifold_to_glb


class TestFullPipeline:
    def test_build_and_export_stl(self, builder, default_params):
        result = builder.build(default_params)
        stl_bytes = manifold_to_stl(result.manifold)
        assert len(stl_bytes) > 84  # STL header is 80 bytes + 4 byte count
        assert stl_bytes[:5] != b"solid"  # binary STL, not ASCII

    def test_build_and_export_glb(self, builder, default_params):
        result = builder.build(default_params)
        glb_bytes = manifold_to_glb(result.manifold)
        assert glb_bytes[:4] == b"glTF"  # GLB magic number

    def test_different_printer_types_produce_different_geometry(self, builder):
        params_fdm = BuildingParams(style="modern", printer_type=PrinterType.FDM)
        params_resin = BuildingParams(style="modern", printer_type=PrinterType.RESIN)
        r1 = builder.build(params_fdm)
        r2 = builder.build(params_resin)
        # Resin allows thinner walls, so geometry may differ
        # At minimum, both should be valid
        assert r1.manifold.volume() > 0
        assert r2.manifold.volume() > 0
```

### API Tests

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from hotel_generator.api import app

client = TestClient(app)


class TestAPI:
    def test_list_styles(self):
        resp = client.get("/styles")
        assert resp.status_code == 200
        styles = resp.json()
        assert len(styles) > 0
        assert all("name" in s for s in styles)

    def test_generate_preview(self):
        resp = client.post("/generate", json={"style": "modern", "floors": 3})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "model/gltf-binary"
        assert resp.content[:4] == b"glTF"

    def test_invalid_params_returns_400(self):
        resp = client.post("/generate", json={"style": "modern", "floors": 100})
        assert resp.status_code == 422  # Pydantic validation

    def test_unknown_style_returns_400(self):
        resp = client.post("/generate", json={"style": "nonexistent"})
        assert resp.status_code == 400

    def test_export_stl(self):
        resp = client.post("/export/stl", json={"style": "modern", "floors": 2})
        assert resp.status_code == 200
        assert "attachment" in resp.headers["content-disposition"]
```

---

## 8. Dependency Injection Patterns

This is a small focused tool, not a Spring application. We do not need a DI container. Instead, we use three simple patterns:

### Pattern 1: Constructor Injection for the Builder

The `HotelBuilder` accepts optional constraint overrides via its constructor. In production, it uses defaults. In tests, you inject test-specific constraints.

```python
# Production
builder = HotelBuilder()

# Test: override FDM constraints to be more permissive
test_constraints = {
    PrinterType.FDM: PrinterConstraints(
        min_wall_thickness=0.1,  # allow thinner for test speed
        min_feature_size=0.1,
        min_column_diameter=0.1,
        min_emboss_depth=0.05,
        max_overhang_angle=90.0,
        cutout_overshoot=0.1,
    ),
}
builder = HotelBuilder(constraints_override=test_constraints)
```

### Pattern 2: Function Parameters for Components

Component functions are pure: they take all dependencies as arguments and return geometry. No global state, no singletons.

```python
# This is easy to test because it depends on nothing external
def solid_wall(width: float, height: float, thickness: float) -> Manifold:
    return box(width, thickness, height)

# This composes functions explicitly -- no hidden lookups
def facade_with_windows(
    wall_width: float,
    wall_height: float,
    wall_thickness: float,
    window_positions: list[tuple[float, float]],
    window_width: float,
    window_height: float,
) -> Manifold:
    wall = solid_wall(wall_width, wall_height, wall_thickness)
    cutouts = [
        translate(
            window_cutout(window_width, window_height, wall_thickness),
            x=x, z=z,
        )
        for x, z in window_positions
    ]
    return wall - union_all(cutouts) if cutouts else wall
```

### Pattern 3: FastAPI Dependency Injection for the API Layer

FastAPI has a built-in dependency injection system. Use it for the builder instance so it can be overridden in API tests.

```python
# src/hotel_generator/api.py
from fastapi import Depends

_builder = HotelBuilder()


def get_builder() -> HotelBuilder:
    return _builder


@app.post("/generate")
async def generate_preview(
    params: BuildingParams,
    builder: HotelBuilder = Depends(get_builder),
):
    result = builder.build(params)
    # ...


# In tests:
from hotel_generator.api import app, get_builder

def get_test_builder():
    return HotelBuilder(constraints_override=test_constraints)

app.dependency_overrides[get_builder] = get_test_builder
```

### What We Deliberately Avoid

- **No abstract factory for components.** Components are functions, not classes. We don't need a `WindowFactory` when `window_cutout(width, height, thickness)` is perfectly clear.
- **No service locator.** The style registry is the one place where we do name-based lookup, and that's because the user literally sends a style name string. Everything else uses direct imports.
- **No DI framework.** `dependency-injector`, `inject`, etc. are overkill. Constructor params and FastAPI's `Depends` cover everything.

---

## 9. Performance Considerations

### Where Time Is Spent

For a typical 3-floor hotel at game-piece scale:

| Phase | Estimated Time | Notes |
|---|---|---|
| Parameter validation | <1ms | Pydantic, pure Python |
| Geometry generation | 10-100ms | manifold3d CSG booleans |
| Export to GLB | 5-20ms | trimesh serialization |
| Export to STL | 5-20ms | trimesh serialization |
| HTTP overhead | <5ms | FastAPI/Uvicorn |

Total: **20-150ms per request**. This is fast enough that caching is a nice-to-have, not a necessity.

### Async Endpoints with Sync Geometry

manifold3d and trimesh are synchronous CPU-bound libraries. FastAPI's default behavior with `async def` endpoints is to run them in the main event loop -- which would block all other requests during geometry generation.

Two viable options:

**Option A: Use `def` (not `async def`) endpoints.** FastAPI automatically runs sync endpoint functions in a thread pool. This is the simplest approach and works well for moderate concurrency.

```python
@app.post("/generate")
def generate_preview(params: BuildingParams):  # Note: def, not async def
    result = builder.build(params)
    glb_bytes = manifold_to_glb(result.manifold)
    return Response(content=glb_bytes, media_type="model/gltf-binary")
```

**Option B: Explicitly run CPU work in a thread pool from async endpoints.** This gives you more control.

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4)

@app.post("/generate")
async def generate_preview(params: BuildingParams):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, builder.build, params)
    glb_bytes = await loop.run_in_executor(_executor, manifold_to_glb, result.manifold)
    return Response(content=glb_bytes, media_type="model/gltf-binary")
```

**Recommendation: Start with Option A.** It is simpler, and the thread pool default (40 threads) is more than sufficient. Move to Option B only if profiling shows contention.

### Response Caching

The same `BuildingParams` always produces the same output (generation is deterministic). We can cache results keyed by a hash of the parameters.

```python
import hashlib
import json
from functools import lru_cache

def _params_hash(params: BuildingParams) -> str:
    """Deterministic hash of building parameters."""
    raw = params.model_dump_json(exclude_none=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# Simple in-memory cache for GLB bytes
_glb_cache: dict[str, bytes] = {}
_MAX_CACHE_ENTRIES = 128


def get_or_generate_glb(params: BuildingParams, builder: HotelBuilder) -> bytes:
    key = _params_hash(params)
    if key in _glb_cache:
        return _glb_cache[key]

    result = builder.build(params)
    glb_bytes = manifold_to_glb(result.manifold)

    # Evict oldest if full (simple strategy)
    if len(_glb_cache) >= _MAX_CACHE_ENTRIES:
        oldest_key = next(iter(_glb_cache))
        del _glb_cache[oldest_key]

    _glb_cache[key] = glb_bytes
    return glb_bytes
```

For a single-user tool, even a 128-entry dict cache eliminates redundant generation when the user tweaks one parameter and then undoes it. No Redis, no external cache -- just a dict.

### Streaming Large STL Files

Most game-piece STL files will be 100KB-2MB. This fits comfortably in memory. However, if someone generates a complex Victorian hotel with many fine details, the STL could reach 5-10MB. For this case, use `StreamingResponse`:

```python
import io

@app.post("/export/stl")
def export_stl(params: BuildingParams):
    result = builder.build(params)
    stl_bytes = manifold_to_stl(result.manifold)

    if len(stl_bytes) > 2_000_000:  # >2MB: stream it
        return StreamingResponse(
            io.BytesIO(stl_bytes),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="hotel.stl"'},
        )
    else:
        return Response(
            content=stl_bytes,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="hotel.stl"'},
        )
```

In practice, `Response(content=stl_bytes)` is fine for everything under 10MB. The streaming approach is here as a pattern for future-proofing, not because it solves an immediate problem.

### Triangle Budget

Add an optional `max_triangles` parameter to `BuildingParams` (default: 50000). If the generated mesh exceeds this, simplify it using trimesh's decimation before export. This prevents a single request from producing absurdly large files.

```python
def simplify_if_needed(manifold: Manifold, max_triangles: int) -> Manifold:
    if manifold.num_tri() <= max_triangles:
        return manifold
    # manifold3d has built-in simplification
    return manifold.refine_to_length(
        manifold.num_tri() / max_triangles * 2  # approximate target edge length
    )
```

---

## 10. Configuration Management

### Printer Profiles

Printer profiles are constants, not user-editable config files. They live in code:

```python
# src/hotel_generator/assembly/building.py
from hotel_generator.config import PrinterType, PrinterConstraints

PRINTER_PROFILES: dict[PrinterType, PrinterConstraints] = {
    PrinterType.FDM: PrinterConstraints(
        min_wall_thickness=0.8,
        min_feature_size=0.6,
        min_column_diameter=0.8,
        min_emboss_depth=0.3,
        max_overhang_angle=45.0,
        cutout_overshoot=0.1,
    ),
    PrinterType.RESIN: PrinterConstraints(
        min_wall_thickness=0.3,
        min_feature_size=0.2,
        min_column_diameter=0.4,
        min_emboss_depth=0.15,
        max_overhang_angle=60.0,
        cutout_overshoot=0.1,
    ),
}
```

**Why not a config file?** These values are engineering constants tied to physics. They should change only when the code is updated. Putting them in a YAML file adds a deployment concern (where is the file? is it in sync with the code?) for no benefit. If we later need user-editable profiles, the `PrinterConstraints` model is already there -- just load it from a JSON file instead of a dict literal.

### Default Parameters

`BuildingParams` has sensible defaults for every field. A bare `POST /generate` with `{}` (empty body) produces a valid 3-floor modern hotel. The defaults are in the Pydantic model itself (via `Field(default=...)`), which means they are visible in the OpenAPI schema and thus in the web UI.

### Style Parameter Schemas

Each style exposes its own parameter schema via `style_params_schema()`. The web UI fetches this from `GET /styles` and dynamically generates form controls.

```python
# What the UI receives from GET /styles:
[
    {
        "name": "modern",
        "display_name": "Modern",
        "description": "Flat roof, grid windows, clean horizontal lines",
        "params_schema": {
            "type": "object",
            "properties": {
                "cantilever_depth": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Depth of upper-floor cantilever overhang (mm)"
                },
                "penthouse": {
                    "type": "boolean",
                    "default": false,
                    "description": "Add a setback penthouse floor"
                }
            }
        }
    },
    {
        "name": "art_deco",
        "display_name": "Art Deco",
        "description": "Stepped ziggurat massing, vertical fins, geometric crown",
        "params_schema": {
            "type": "object",
            "properties": {
                "step_count": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 6,
                    "description": "Number of stepped setbacks"
                },
                "fin_count": {
                    "type": "integer",
                    "default": 4,
                    "minimum": 0,
                    "maximum": 10,
                    "description": "Number of vertical decorative fins"
                }
            }
        }
    }
]
```

The web UI interprets this schema to render:
- `type: number` as a slider with the range from the base `BuildingParams` constraints.
- `type: integer` with `minimum`/`maximum` as a bounded slider.
- `type: boolean` as a checkbox.
- `description` as a tooltip.

### Environment Configuration

Server configuration (host, port, CORS origins) uses environment variables, not config files. Pydantic's `BaseSettings` handles this cleanly:

```python
# src/hotel_generator/settings.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:8000"]
    log_level: str = "info"
    max_concurrent_builds: int = 4
    cache_max_entries: int = 128

    model_config = {"env_prefix": "HOTEL_"}


settings = Settings()
```

Usage: `HOTEL_PORT=9000 HOTEL_LOG_LEVEL=debug uvicorn hotel_generator.api:app`

---

## Appendix A: Key Library Interfaces

For reference, here are the core manifold3d and trimesh interfaces this architecture relies on.

### manifold3d

```python
from manifold3d import Manifold, Mesh, CrossSection

# Primitives
cube = Manifold.cube([w, d, h])            # axis-aligned box at origin
cyl = Manifold.cylinder(height, radius)     # Z-axis cylinder

# Booleans
result = a + b                              # union
result = a - b                              # difference
result = a ^ b                              # intersection

# Batch booleans (faster than sequential)
result = Manifold.batch_boolean(manifolds, OpType.Add)

# Transforms
moved = m.translate([x, y, z])
rotated = m.rotate([0, 0, angle_degrees])
mirrored = m.mirror([1, 0, 0])             # mirror across YZ plane

# Extrusion
cross = CrossSection([[x1,y1], [x2,y2], ...])  # 2D polygon
solid = Manifold.extrude(cross, height)

# Mesh export
mesh = m.to_mesh()                          # -> Mesh with vert_properties, tri_verts
```

### trimesh

```python
import trimesh
import numpy as np

# From manifold3d mesh to trimesh
mesh = manifold.to_mesh()
tm = trimesh.Trimesh(
    vertices=mesh.vert_properties[:, :3],
    faces=mesh.tri_verts,
)

# Export
stl_bytes = tm.export(file_type="stl")     # binary STL
glb_bytes = tm.export(file_type="glb")     # binary glTF
```

---

## Appendix B: Data Flow Diagram

```
User (Web UI)
    │
    │  POST /generate  { "style": "art_deco", "floors": 4, ... }
    ▼
FastAPI (api.py)
    │
    │  Pydantic validation (BuildingParams)
    │  ✗ → 400/422 JSON error
    │  ✓
    ▼
HotelBuilder.build(params)
    │
    │  1. Resolve PrinterConstraints from printer_type
    │  2. get_style(params.style) → ArtDecoStyle instance
    │  3. style.generate(params, constraints)
    │     │
    │     │  ┌── Phase 1: Build shell ──────────────────┐
    │     │  │ box(w, d, h)                              │
    │     │  │ - union_all(window_cutouts + door_cutouts)│
    │     │  └──────────────────────────────────────────┘
    │     │  ┌── Phase 2: Add features ─────────────────┐
    │     │  │ + union_all(roof, slabs, fins, columns)   │
    │     │  └──────────────────────────────────────────┘
    │     │  → Manifold
    │     │
    │  4. validate_mesh(manifold, constraints)
    │  5. Return BuildResult
    │
    ▼
Export (export/glb.py)
    │
    │  Manifold → trimesh.Trimesh → GLB bytes
    ▼
HTTP Response
    │  Content-Type: model/gltf-binary
    │  X-Build-Metadata: {"triangle_count": 1842, ...}
    ▼
Web UI (three.js)
    │  GLTFLoader → Scene → Render with OrbitControls
```

---

## Appendix C: Decision Log

| Decision | Choice | Alternatives Considered | Rationale |
|---|---|---|---|
| Geometry engine | manifold3d | build123d, CadQuery, OpenSCAD | 10x smaller install, guaranteed watertight, fast booleans |
| Mesh I/O | trimesh | numpy-stl, meshio | GLB support, validation utilities, well-maintained |
| Web framework | FastAPI | Flask, Django | Async capable, auto OpenAPI docs, Pydantic native |
| Style extensibility | Strategy pattern + registry | Plugin system, YAML config | Simple, explicit, no dynamic loading complexity |
| Config validation | Pydantic models | dataclasses + manual, attrs | JSON Schema generation, FastAPI integration, rich validation |
| DI approach | Constructor injection + FastAPI Depends | DI container, service locator | Minimal overhead, sufficient for project scope |
| Caching | In-memory dict | Redis, diskcache | Single-user tool, no persistence needed |
| Printer profiles | Code constants | YAML/JSON files, database | Engineering constants, change with code not deployment |
| Build orchestration | Builder class | Pipeline function, chain-of-responsibility | Holds printer config state, single entry point for API |
| Error handling | Custom exception hierarchy + FastAPI handlers | Generic HTTP exceptions, middleware | Clean separation of domain errors from HTTP concerns |

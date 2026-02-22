"""FastAPI application with hotel generation endpoints."""

import json
import logging

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from hotel_generator.assembly.building import HotelBuilder
from hotel_generator.board.board_builder import BoardBuilder
from hotel_generator.board.config import BoardParams, PropertyParams
from hotel_generator.board.property_builder import PropertyBuilder
from hotel_generator.complex.builder import ComplexBuilder
from hotel_generator.complex.presets import list_presets
from hotel_generator.config import BuildingParams, ComplexParams, ErrorResponse
from hotel_generator.errors import (
    GeometryError,
    HotelGeneratorError,
    InvalidParamsError,
)
from hotel_generator.export.glb import export_glb_bytes
from hotel_generator.export.stl import (
    export_board_to_directory,
    export_property_to_directory,
    export_stl_bytes,
    export_complex_to_directory,
)
from hotel_generator.settings import Settings
from hotel_generator.styles.base import list_styles

logger = logging.getLogger(__name__)

# Create app
app = FastAPI(title="3D Hotel Generator", version="0.1.0")

# Settings
settings = Settings()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Error handlers
@app.exception_handler(InvalidParamsError)
async def invalid_params_handler(request: Request, exc: InvalidParamsError):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error_type="InvalidParamsError",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(GeometryError)
async def geometry_error_handler(request: Request, exc: GeometryError):
    logger.exception("Geometry error during generation")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_type="GeometryError",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(HotelGeneratorError)
async def general_error_handler(request: Request, exc: HotelGeneratorError):
    logger.exception("Hotel generator error")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_type=type(exc).__name__,
            message=str(exc),
        ).model_dump(),
    )


# Dependency injection
def get_builder() -> HotelBuilder:
    """Provide a HotelBuilder instance. Overridable in tests."""
    return HotelBuilder(settings)


def get_complex_builder() -> ComplexBuilder:
    """Provide a ComplexBuilder instance. Overridable in tests."""
    return ComplexBuilder(settings)


def get_property_builder() -> PropertyBuilder:
    """Provide a PropertyBuilder instance. Overridable in tests."""
    return PropertyBuilder(settings)


def get_board_builder() -> BoardBuilder:
    """Provide a BoardBuilder instance. Overridable in tests."""
    return BoardBuilder(settings)


# API routes (sync def for CPU-bound work)
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/styles")
def get_styles():
    """List all available architectural styles."""
    return {"styles": list_styles()}


@app.post("/generate")
def generate(params: BuildingParams, builder: HotelBuilder = Depends(get_builder)):
    """Generate a hotel and return GLB bytes for 3D preview.

    Returns binary GLB with X-Build-Metadata header containing
    triangle count, bounding box, watertightness, and warnings.
    """
    result = builder.build(params)
    glb_bytes = export_glb_bytes(result.manifold)

    metadata = {
        "triangle_count": result.triangle_count,
        "bounding_box": list(result.bounding_box),
        "is_watertight": result.is_watertight,
        "warnings": result.warnings,
    }

    return Response(
        content=glb_bytes,
        media_type="application/octet-stream",
        headers={"X-Build-Metadata": json.dumps(metadata)},
    )


@app.post("/export/stl")
def export_stl(params: BuildingParams, builder: HotelBuilder = Depends(get_builder)):
    """Generate a hotel and return STL file for 3D printing."""
    result = builder.build(params)
    stl_bytes = export_stl_bytes(result.manifold)

    filename = f"hotel_{params.style_name}_{params.seed}.stl"

    return Response(
        content=stl_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


PREVIEW_ANGLE_MAP = {
    "front_3q": (45, 30, "front_3q"),
    "back_3q": (135, 30, "back_3q"),
    "front": (0, 0, "front"),
    "top": (0, 80, "top"),
}


@app.post("/preview/png")
def preview_png(
    params: BuildingParams,
    angle: str = Query(default="front_3q", description="Camera angle name"),
    resolution: int = Query(default=512, ge=128, le=2048, description="Image resolution (square)"),
    builder: HotelBuilder = Depends(get_builder),
):
    """Generate a hotel and return a PNG preview image."""
    if angle not in PREVIEW_ANGLE_MAP:
        raise InvalidParamsError(
            f"Unknown angle: {angle!r}. Use one of: {list(PREVIEW_ANGLE_MAP.keys())}"
        )

    result = builder.build(params)

    try:
        from scripts.render_hotel import render_manifold_to_png_bytes
    except ImportError:
        # Fall back to direct import path when scripts/ is not a package
        import importlib.util
        import pathlib as _pl

        spec = importlib.util.spec_from_file_location(
            "render_hotel",
            _pl.Path(__file__).parent.parent.parent / "scripts" / "render_hotel.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        render_manifold_to_png_bytes = mod.render_manifold_to_png_bytes

    png_bytes = render_manifold_to_png_bytes(
        result.manifold,
        resolution=(resolution, resolution),
        angle=PREVIEW_ANGLE_MAP[angle],
    )

    return Response(content=png_bytes, media_type="image/png")


@app.get("/presets")
def get_presets():
    """List all available hotel complex presets."""
    return {"presets": [p.model_dump() for p in list_presets()]}


@app.post("/complex/generate")
def complex_generate(
    params: ComplexParams,
    builder: ComplexBuilder = Depends(get_complex_builder),
):
    """Generate a hotel complex and return combined GLB for 3D preview.

    Returns binary GLB with X-Complex-Metadata header containing
    building count, lot size, generation time, and per-building info.
    """
    result = builder.build(params)
    glb_bytes = export_glb_bytes(result.combined)

    metadata = {
        "num_buildings": len(result.buildings),
        "lot_width": result.lot_width,
        "lot_depth": result.lot_depth,
        "buildings": [
            {
                "triangle_count": b.triangle_count,
                "is_watertight": b.is_watertight,
                "role": result.placements[i].role,
            }
            for i, b in enumerate(result.buildings)
        ],
        **result.metadata,
    }

    return Response(
        content=glb_bytes,
        media_type="application/octet-stream",
        headers={"X-Complex-Metadata": json.dumps(metadata)},
    )


@app.post("/complex/export")
def complex_export(
    params: ComplexParams,
    builder: ComplexBuilder = Depends(get_complex_builder),
):
    """Generate a hotel complex and export STL files to output directory.

    Returns JSON with file list and output path.
    """
    result = builder.build(params)

    import tempfile
    output_dir = tempfile.mkdtemp(prefix="hotel_complex_")
    files = export_complex_to_directory(result, output_dir)

    return {
        "output_dir": output_dir,
        "files": files,
        "num_buildings": len(result.buildings),
        "lot_width": result.lot_width,
        "lot_depth": result.lot_depth,
        "metadata": result.metadata,
    }


# --- Property plate endpoints ---

@app.post("/property/generate")
def property_generate(
    params: PropertyParams,
    builder: PropertyBuilder = Depends(get_property_builder),
):
    """Generate a property plate (buildings + garden + road strip) as GLB preview."""
    result = builder.build(params)
    glb_bytes = export_glb_bytes(result.plate)

    metadata = {
        "lot_width": result.lot_width,
        "lot_depth": result.lot_depth,
        "num_buildings": len(result.buildings),
        "num_garden_features": len(result.garden_placements),
        **result.metadata,
    }

    return Response(
        content=glb_bytes,
        media_type="application/octet-stream",
        headers={"X-Property-Metadata": json.dumps(metadata)},
    )


@app.post("/property/export")
def property_export(
    params: PropertyParams,
    builder: PropertyBuilder = Depends(get_property_builder),
):
    """Export a property plate as separate STL files to output directory."""
    result = builder.build(params)

    import tempfile
    output_dir = tempfile.mkdtemp(prefix="hotel_property_")
    files = export_property_to_directory(result, output_dir)

    return {
        "output_dir": output_dir,
        "files": files,
        "num_buildings": len(result.buildings),
        "num_garden_features": len(result.garden_placements),
        "metadata": result.metadata,
    }


# --- Board endpoints ---

@app.post("/board/generate")
def board_generate(
    params: BoardParams,
    builder: BoardBuilder = Depends(get_board_builder),
):
    """Generate a full game board. Returns metadata JSON (plates are too large for single GLB)."""
    result = builder.build(params)

    return {
        "num_properties": len(result.properties),
        "road_shape": result.road_shape,
        "property_slots": [
            {
                "index": s.index,
                "center_x": s.center_x,
                "center_y": s.center_y,
                "road_edge": s.road_edge,
                "preset": s.assigned_preset,
            }
            for s in result.property_slots
        ],
        "metadata": result.metadata,
    }


@app.post("/board/preview")
def board_preview(
    params: BoardParams,
    builder: BoardBuilder = Depends(get_board_builder),
):
    """Generate a full game board and return assembled GLB for 3D preview.

    Combines all property plates + frame pieces into a single model
    positioned according to the road layout.
    """
    from hotel_generator.geometry.booleans import compose_disjoint
    from hotel_generator.geometry.transforms import translate as geo_translate

    result = builder.build(params)

    # Assemble all pieces into board coordinates
    parts = []
    for prop, slot in zip(result.properties, result.property_slots):
        placed = geo_translate(prop.plate, x=slot.center_x, y=slot.center_y)
        parts.append(placed)

    # Add frame pieces (already positioned in board coordinates)
    if result.frame:
        for piece in result.frame.all_pieces:
            parts.append(piece.manifold)

    assembled = compose_disjoint(parts)
    glb_bytes = export_glb_bytes(assembled)

    metadata = {
        "num_properties": len(result.properties),
        "road_shape": result.road_shape,
        "num_frame_pieces": len(result.frame.all_pieces) if result.frame else 0,
        "property_slots": [
            {"index": s.index, "preset": s.assigned_preset}
            for s in result.property_slots
        ],
        **result.metadata,
    }

    return Response(
        content=glb_bytes,
        media_type="application/octet-stream",
        headers={"X-Board-Metadata": json.dumps(metadata)},
    )


@app.post("/board/export")
def board_export(
    params: BoardParams,
    builder: BoardBuilder = Depends(get_board_builder),
):
    """Export all property plates to output directory."""
    result = builder.build(params)

    import tempfile
    output_dir = tempfile.mkdtemp(prefix="hotel_board_")
    files = export_board_to_directory(result, output_dir)

    return {
        "output_dir": output_dir,
        "files": files,
        "num_properties": len(result.properties),
        "metadata": result.metadata,
    }


# Static files mount (MUST be after API routes)
import pathlib

web_dir = pathlib.Path(__file__).parent.parent.parent / "web"
if web_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="static")

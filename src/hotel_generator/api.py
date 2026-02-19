"""FastAPI application with hotel generation endpoints."""

import json
import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from hotel_generator.assembly.building import HotelBuilder
from hotel_generator.config import BuildingParams, ErrorResponse
from hotel_generator.errors import (
    GeometryError,
    HotelGeneratorError,
    InvalidParamsError,
)
from hotel_generator.export.glb import export_glb_bytes
from hotel_generator.export.stl import export_stl_bytes
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


# Static files mount (MUST be after API routes)
import pathlib

web_dir = pathlib.Path(__file__).parent.parent.parent / "web"
if web_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="static")

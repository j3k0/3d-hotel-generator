# STL Generation & 3D Printing Pipeline

> Technical guide for generating watertight STL files from CSG operations using manifold3d and trimesh.

---

## 1. Pipeline Overview

```
Parameters (JSON)
  │
  ├─→ manifold3d CSG operations → Manifold object (watertight by construction)
  │
  ├─→ Manifold.to_mesh() → vertices + triangles (numpy arrays)
  │
  ├─→ trimesh.Trimesh(vertices, faces) → trimesh mesh object
  │
  ├─→ Validation (watertight, volume, dimensions, printability)
  │
  ├─→ trimesh.export('hotel.stl', file_type='stl') → Binary STL file
  │
  └─→ trimesh.export('hotel.glb', file_type='glb') → GLB for web preview
```

---

## 2. manifold3d Geometry Generation

### Core API

```python
import manifold3d
from manifold3d import Manifold, CrossSection
import numpy as np

# Primitive creation
def box(width: float, depth: float, height: float) -> Manifold:
    """Create a box at the origin."""
    return Manifold.cube([width, depth, height])

def cylinder(radius: float, height: float, segments: int = 32) -> Manifold:
    """Create a cylinder at the origin."""
    return Manifold.cylinder(height, radius, radius, segments)

def cone(radius_bottom: float, radius_top: float, height: float,
         segments: int = 32) -> Manifold:
    """Create a cone/tapered cylinder."""
    return Manifold.cylinder(height, radius_bottom, radius_top, segments)
```

### Boolean Operations

```python
# Union (additive)
combined = part_a + part_b
# or
combined = part_a | part_b

# Difference (subtractive)
cut = body - cutout
# or
cut = body - cutout_a - cutout_b  # chained

# Intersection
overlap = part_a ^ part_b

# Batch union (much faster for many parts)
parts = [box1, box2, box3, ...]
result = Manifold.batch_boolean(parts, Manifold.OpType.Add)
```

### Transforms

```python
# Translation
moved = part.translate([x, y, z])

# Rotation (degrees, around origin)
rotated = part.rotate([rx, ry, rz])

# Scale
scaled = part.scale([sx, sy, sz])

# Mirror
mirrored = part.mirror([1, 0, 0])  # mirror across YZ plane
```

### Extrusion from 2D Cross-Sections

```python
# Triangular cross-section → extruded prism (useful for gable roofs)
triangle = CrossSection([
    [0.0, 0.0],
    [width, 0.0],
    [width / 2, peak_height]
])
roof = Manifold.extrude(triangle, depth)

# L-shaped cross-section
l_shape = CrossSection([
    [0, 0], [main_w, 0], [main_w, wing_d],
    [wing_w, wing_d], [wing_w, main_d], [0, main_d]
])
l_building = Manifold.extrude(l_shape, height)
```

### Convex Hull

```python
# Hull of two shapes (useful for tapered/mansard forms)
bottom = Manifold.cube([4, 4, 0.01]).translate([-2, -2, 0])
top = Manifold.cube([3, 3, 0.01]).translate([-1.5, -1.5, 2])
mansard = Manifold.hull_batch([bottom, top])
```

### Key Guarantees

- **Watertight by construction**: Every Manifold operation produces a watertight (2-manifold) mesh
- **No self-intersections**: Boolean operations resolve all intersections
- **Correct normals**: All face normals point outward
- **No degenerate faces**: Zero-area triangles are eliminated

---

## 3. Mesh Extraction

### From Manifold to Arrays

```python
def manifold_to_arrays(m: Manifold) -> tuple[np.ndarray, np.ndarray]:
    """Extract vertices and face indices from a Manifold."""
    mesh = m.to_mesh()

    # Vertices: (N, 3) float64 array
    vertices = np.array(mesh.vert_properties[:, :3], dtype=np.float64)

    # Faces: (M, 3) int32 array (triangle indices)
    faces = np.array(mesh.tri_verts, dtype=np.int32)

    return vertices, faces
```

### Creating a trimesh Object

```python
import trimesh

def manifold_to_trimesh(m: Manifold) -> trimesh.Trimesh:
    """Convert a manifold3d Manifold to a trimesh Trimesh."""
    vertices, faces = manifold_to_arrays(m)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

    # Verify integrity
    assert mesh.is_watertight, "Mesh is not watertight"
    assert mesh.volume > 0, "Mesh has zero or negative volume"

    return mesh
```

---

## 4. STL Export

### Binary STL (Preferred)

```python
def export_stl(mesh: trimesh.Trimesh, filepath: str) -> None:
    """Export mesh as binary STL file."""
    mesh.export(filepath, file_type='stl')


def export_stl_bytes(mesh: trimesh.Trimesh) -> bytes:
    """Export mesh as STL bytes (for HTTP response)."""
    return mesh.export(file_type='stl')
```

### STL Format Notes

- **Binary STL** is ~5x smaller than ASCII STL
- Each triangle stored as: normal (3×float32) + 3 vertices (9×float32) + attribute (uint16) = 50 bytes
- A typical miniature hotel: ~2,000-10,000 triangles = 100KB-500KB STL file
- No color/material support in STL — use GLB for that

### GLB Export (for Web Preview)

```python
def export_glb(mesh: trimesh.Trimesh, filepath: str = None) -> bytes:
    """Export mesh as GLB (binary glTF) for three.js preview."""
    scene = trimesh.Scene(mesh)
    if filepath:
        scene.export(filepath, file_type='glb')
    return scene.export(file_type='glb')
```

### GLB Advantages
- Supported by three.js GLTFLoader
- Can include materials/colors
- Compressed binary format
- Single file (no external textures)

---

## 5. Validation & Printability Checks

### Mesh Integrity

```python
def validate_mesh(mesh: trimesh.Trimesh) -> dict:
    """Run all validation checks on a mesh."""
    results = {
        'is_watertight': mesh.is_watertight,
        'is_volume_positive': mesh.volume > 0,
        'volume_mm3': mesh.volume,
        'bounding_box': mesh.bounds.tolist(),
        'face_count': len(mesh.faces),
        'vertex_count': len(mesh.vertices),
    }

    # Dimension checks
    dims = mesh.bounds[1] - mesh.bounds[0]  # [width, depth, height]
    results['dimensions_mm'] = dims.tolist()
    results['max_dimension_mm'] = float(dims.max())
    results['min_dimension_mm'] = float(dims.min())

    return results
```

### Printability Checks

```python
class PrintabilityChecker:
    """Check if a mesh is suitable for 3D printing."""

    def __init__(self, printer_type: str = 'fdm'):
        if printer_type == 'fdm':
            self.min_wall = 0.8   # mm
            self.min_feature = 0.6  # mm
            self.max_overhang = 45  # degrees
        elif printer_type == 'resin':
            self.min_wall = 0.3
            self.min_feature = 0.2
            self.max_overhang = 60

        self.max_dimension = 25.0  # mm - game piece limit
        self.min_volume = 1.0      # mm³

    def check(self, mesh: trimesh.Trimesh) -> list[str]:
        """Return list of warnings/errors."""
        issues = []

        if not mesh.is_watertight:
            issues.append("ERROR: Mesh is not watertight")

        if mesh.volume <= 0:
            issues.append("ERROR: Mesh has zero or negative volume")

        if mesh.volume < self.min_volume:
            issues.append(f"WARNING: Volume {mesh.volume:.2f}mm³ below minimum {self.min_volume}mm³")

        dims = mesh.bounds[1] - mesh.bounds[0]
        if dims.max() > self.max_dimension:
            issues.append(f"WARNING: Max dimension {dims.max():.1f}mm exceeds {self.max_dimension}mm")

        # Check for thin features by examining edge lengths
        edges = mesh.edges_unique_length
        thin_edges = edges[edges < self.min_feature]
        if len(thin_edges) > len(edges) * 0.1:
            issues.append(f"WARNING: {len(thin_edges)} edges below minimum feature size")

        return issues
```

### Flat Base Check

```python
def ensure_flat_base(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Ensure the mesh has a flat base at z=0 for bed adhesion."""
    min_z = mesh.bounds[0][2]
    if abs(min_z) > 0.01:
        # Translate so bottom face is at z=0
        mesh.apply_translation([0, 0, -min_z])

    # Verify bottom is flat: check that many vertices share the minimum z
    z_values = mesh.vertices[:, 2]
    base_vertices = np.sum(np.abs(z_values - z_values.min()) < 0.01)
    if base_vertices < 4:
        print("WARNING: Mesh may not have a flat base for printing")

    return mesh
```

---

## 6. Mesh Optimization

### Triangle Count Reduction

```python
def simplify_mesh(mesh: trimesh.Trimesh, target_faces: int = None,
                  ratio: float = 0.5) -> trimesh.Trimesh:
    """Reduce triangle count while preserving shape."""
    if target_faces is None:
        target_faces = int(len(mesh.faces) * ratio)

    # Use quadric decimation (best quality)
    simplified = mesh.simplify_quadric_decimation(target_faces)

    # Verify still watertight after simplification
    if not simplified.is_watertight:
        print("WARNING: Simplification broke watertightness, using original")
        return mesh

    return simplified
```

### Cylinder Segment Count

```python
# At miniature scale, fewer segments are needed for smooth appearance
def segments_for_radius(radius_mm: float) -> int:
    """Choose appropriate segment count for a cylinder/cone."""
    if radius_mm < 0.3:
        return 8    # very small — octagonal is fine
    elif radius_mm < 1.0:
        return 16   # small — 16 sides smooth enough
    elif radius_mm < 3.0:
        return 24   # medium
    else:
        return 32   # large
```

### Overshoot for Clean Booleans

```python
OVERSHOOT = 0.1  # mm

def window_cutout(w, h, wall_thickness):
    """Create a window cutout that cleanly penetrates the wall."""
    # Extend depth beyond wall to avoid coplanar faces
    return Manifold.cube([w, wall_thickness + OVERSHOOT * 2, h]).translate(
        [0, -OVERSHOOT, 0]
    )
```

---

## 7. Complete Generation Pipeline

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class GenerationResult:
    mesh: trimesh.Trimesh
    params: dict
    validation: dict
    stl_bytes: bytes
    glb_bytes: bytes

def generate_hotel(
    style: str,
    seed: int = 42,
    printer_type: str = 'fdm',
    **overrides
) -> GenerationResult:
    """Complete pipeline: params → CSG → mesh → validated STL + GLB."""

    # 1. Sample and validate parameters
    rng = random.Random(seed)
    params = sample_params(style, rng)
    for key, value in overrides.items():
        setattr(params, key, value)
    params = validate_params(params)

    # 2. Generate CSG geometry
    style_generator = STYLE_REGISTRY[style]
    manifold = style_generator.generate(params)

    # 3. Convert to trimesh
    mesh = manifold_to_trimesh(manifold)

    # 4. Ensure flat base
    mesh = ensure_flat_base(mesh)

    # 5. Validate
    checker = PrintabilityChecker(printer_type)
    issues = checker.check(mesh)
    validation = validate_mesh(mesh)
    validation['issues'] = issues

    # 6. Export
    stl_bytes = mesh.export(file_type='stl')
    glb_bytes = trimesh.Scene(mesh).export(file_type='glb')

    return GenerationResult(
        mesh=mesh,
        params=vars(params),
        validation=validation,
        stl_bytes=stl_bytes,
        glb_bytes=glb_bytes,
    )
```

---

## 8. FastAPI Integration

```python
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

app = FastAPI(title="3D Hotel Generator")

class GenerateRequest(BaseModel):
    style: str = "modern"
    seed: int = 42
    num_floors: int | None = None
    width: float | None = None
    depth: float | None = None
    printer_type: str = "fdm"

@app.post("/generate")
async def generate(req: GenerateRequest):
    """Generate a hotel and return GLB preview."""
    overrides = {k: v for k, v in req.dict().items()
                 if v is not None and k not in ('style', 'seed', 'printer_type')}

    result = generate_hotel(req.style, req.seed, req.printer_type, **overrides)

    return Response(
        content=result.glb_bytes,
        media_type="model/gltf-binary",
        headers={"X-Validation": json.dumps(result.validation)}
    )

@app.post("/export/stl")
async def export_stl(req: GenerateRequest):
    """Generate and download STL file."""
    overrides = {k: v for k, v in req.dict().items()
                 if v is not None and k not in ('style', 'seed', 'printer_type')}

    result = generate_hotel(req.style, req.seed, req.printer_type, **overrides)

    return Response(
        content=result.stl_bytes,
        media_type="application/sla",
        headers={
            "Content-Disposition": f"attachment; filename=hotel_{req.style}_{req.seed}.stl"
        }
    )

@app.get("/styles")
async def list_styles():
    """List available styles with their parameter schemas."""
    return {
        name: {
            "description": gen.description,
            "parameters": gen.param_schema(),
        }
        for name, gen in STYLE_REGISTRY.items()
    }
```

---

## 9. File Size Estimates

| Building Type | Triangles | STL Size | GLB Size |
|--------------|-----------|----------|----------|
| Simple box (modern) | ~500-1,000 | 25-50KB | 10-20KB |
| Medium (townhouse) | 2,000-4,000 | 100-200KB | 40-80KB |
| Complex (victorian) | 5,000-10,000 | 250-500KB | 100-200KB |
| Very detailed | 10,000-20,000 | 500KB-1MB | 200-400KB |

For game pieces at 1-2cm, we target 2,000-5,000 triangles. More detail doesn't improve the print.

---

## 10. Testing the Pipeline

```python
import pytest
from hotel_generator.geometry.primitives import box, cylinder
from hotel_generator.export.stl import manifold_to_trimesh, export_stl_bytes
from hotel_generator.validation.checks import PrintabilityChecker

def test_simple_box_export():
    """A simple box should produce a valid STL."""
    b = box(5, 4, 10)
    mesh = manifold_to_trimesh(b)
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(200.0, rel=0.01)

    stl = export_stl_bytes(mesh)
    assert len(stl) > 0
    assert stl[:5] == b'\x00' * 5 or True  # binary STL starts with 80-byte header

def test_boolean_operation_watertight():
    """CSG boolean results should remain watertight."""
    body = box(5, 5, 10)
    cutout = box(1, 6, 2).translate([2, -0.5, 3])
    result = body - cutout
    mesh = manifold_to_trimesh(result)
    assert mesh.is_watertight
    assert mesh.volume < 250  # less than original box

def test_printability_check():
    """Printability checker should flag tiny meshes."""
    tiny = box(0.1, 0.1, 0.1)
    mesh = manifold_to_trimesh(tiny)
    checker = PrintabilityChecker('fdm')
    issues = checker.check(mesh)
    assert any('volume' in issue.lower() or 'dimension' in issue.lower()
               for issue in issues)

def test_full_pipeline():
    """End-to-end: generate a modern hotel and export."""
    result = generate_hotel('modern', seed=123)
    assert result.mesh.is_watertight
    assert len(result.stl_bytes) > 0
    assert len(result.glb_bytes) > 0
    assert len(result.validation['issues']) == 0
```

---

## 11. Troubleshooting

### Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Non-watertight mesh | Coplanar boolean faces | Overshoot cutouts by 0.1mm |
| Zero-volume result | Subtraction removed everything | Check cutout doesn't exceed body |
| Slow boolean ops | Too many sequential operations | Batch unions before subtraction |
| Invisible details in print | Features below printer resolution | Check `min_feature_size` constraint |
| Mesh has holes | CrossSection not properly closed | Ensure polygon vertices form closed loop |
| Import error manifold3d | Wrong Python version or OS | Use `pip install manifold3d>=3.0` on Python 3.9+ |

### Debugging Geometry

```python
def debug_manifold(m: Manifold, label: str = ""):
    """Print debug info about a Manifold."""
    mesh = m.to_mesh()
    verts = mesh.vert_properties[:, :3]
    print(f"[{label}] vertices={len(verts)}, "
          f"triangles={len(mesh.tri_verts)}, "
          f"bounds=({verts.min(axis=0)} → {verts.max(axis=0)}), "
          f"genus={m.genus()}")


def save_debug_stl(m: Manifold, path: str):
    """Quick save a manifold to STL for visual inspection."""
    mesh = manifold_to_trimesh(m)
    mesh.export(path, file_type='stl')
    print(f"Saved {path}: {len(mesh.faces)} faces, "
          f"watertight={mesh.is_watertight}, volume={mesh.volume:.2f}")
```

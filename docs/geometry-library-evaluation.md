# Geometry Library Evaluation: manifold3d + trimesh

**Version tested:** manifold3d 3.3.2, trimesh 4.11.2, numpy 2.4.2
**Date:** 2026-02-18
**Purpose:** Evaluate manifold3d as the CSG engine for procedurally generating 3D-printable miniature hotel game pieces (~1-2cm tall) exported as STL/GLB.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Key Classes and Constructors](#2-key-classes-and-constructors)
3. [Creating Primitives](#3-creating-primitives)
4. [Boolean Operations](#4-boolean-operations)
5. [Transform Operations](#5-transform-operations)
6. [Mesh Extraction](#6-mesh-extraction)
7. [Integration with trimesh for Export](#7-integration-with-trimesh-for-export)
8. [Common Pitfalls](#8-common-pitfalls)
9. [Performance Tips](#9-performance-tips)
10. [Limitations and Workarounds](#10-limitations-and-workarounds)
11. [Verdict](#11-verdict)

---

## 1. Architecture Overview

manifold3d is a C++ geometry kernel with Python bindings (via nanobind). It provides:

- **Guaranteed manifold (watertight) output** from all boolean operations -- the single most important property for 3D printing workflows.
- **Lazy transform evaluation** -- translate/rotate/scale are combined and applied only when geometry is actually needed.
- **Efficient CSG via an internal BVH** -- bounding volume hierarchy accelerates boolean intersection testing.
- **~1.2 MB wheel** -- dramatically smaller than OpenCascade-based alternatives (~200 MB+).

The library exposes two primary geometry types:

| Type | Dimension | Purpose |
|------|-----------|---------|
| `CrossSection` | 2D | Closed polygonal regions (with holes), used as extrusion profiles |
| `Manifold` | 3D | Watertight solid meshes, the main output type |

Supporting types:

| Type | Purpose |
|------|---------|
| `Mesh` | Raw triangle mesh data (vertices + faces as numpy arrays) |
| `OpType` | Enum for boolean operations: `Add`, `Subtract`, `Intersect` |
| `JoinType` | Enum for offset corner treatment: `Round`, `Miter`, `Bevel`, `Square` |
| `FillRule` | Enum for polygon fill rules |
| `Error` | Enum for mesh validity errors |

---

## 2. Key Classes and Constructors

### 2.1 Manifold -- The Core 3D Solid

Every `Manifold` instance represents a guaranteed-watertight 3D solid (or an empty solid on error). There is no way to construct a non-manifold `Manifold` -- invalid input produces an empty result with an error status.

**Static constructors (primitives):**

```python
from manifold3d import Manifold

box    = Manifold.cube([width, depth, height], center=False)
cyl    = Manifold.cylinder(height, radius_low, radius_high=-1, circular_segments=0, center=False)
sph    = Manifold.sphere(radius, circular_segments=0)
tet    = Manifold.tetrahedron()
```

**Constructors from other data:**

```python
solid  = Manifold.extrude(cross_section, height, n_divisions=0, twist_degrees=0, scale_top=(1,1))
solid  = Manifold.revolve(cross_section, circular_segments=0, revolve_degrees=360)
solid  = Manifold.smooth(mesh, sharpened_edges=[], edge_smoothness=[])
solid  = Manifold.level_set(sdf_func, bounds, edge_length, level=0, tolerance=-1)
solid  = Manifold.compose([manifold_a, manifold_b, ...])   # non-overlapping solids into one
solid  = Manifold.hull_points([[x,y,z], ...])               # convex hull from points
solid  = Manifold.batch_hull([manifold_a, manifold_b, ...]) # convex hull enveloping solids
```

**From raw mesh data:**

```python
from manifold3d import Mesh
import numpy as np

mesh = Mesh(
    vert_properties=np.array([[x,y,z], ...], dtype=np.float32),  # shape (N, 3+)
    tri_verts=np.array([[v0,v1,v2], ...], dtype=np.uint32)       # shape (M, 3)
)
solid = Manifold(mesh)  # returns empty if not manifold; check .status()
```

**Querying state:**

```python
solid.status()        # Error.NoError if valid
solid.is_empty()      # True if zero volume
solid.volume()        # float, mm^3
solid.surface_area()  # float, mm^2
solid.bounding_box()  # (min_x, min_y, min_z, max_x, max_y, max_z)
solid.num_tri()       # int, triangle count
solid.num_vert()      # int, vertex count
solid.genus()         # int, topological genus (0 for a simple solid)
```

### 2.2 CrossSection -- 2D Profiles

`CrossSection` represents one or more closed 2D polygonal contours, potentially with holes. It is the input to `Manifold.extrude()` and `Manifold.revolve()`.

```python
from manifold3d import CrossSection

rect   = CrossSection.square([width, height], center=False)
circ   = CrossSection.circle(radius, circular_segments=0)

# From polygon vertices (list of contours; outer CCW, holes CW)
profile = CrossSection([
    [[0,0], [10,0], [10,8], [5,12], [0,8]],  # outer contour
    # [[3,3], [7,3], [7,7], [3,7]]            # optional hole (clockwise)
])
```

**CrossSection operations:**

```python
cs.area()                  # float
cs.bounds()                # (min_x, min_y, max_x, max_y)
cs.num_vert()              # int
cs.num_contour()           # int
cs.to_polygons()           # list of numpy arrays, one per contour
cs.is_empty()              # bool

# Boolean ops (same syntax as Manifold)
union      = cs_a + cs_b
difference = cs_a - cs_b
intersect  = cs_a ^ cs_b

# Offset (grow/shrink) -- critical for rounded-corner profiles
grown  = cs.offset(delta=1.0, join_type=JoinType.Round, circular_segments=16)
shrunk = cs.offset(delta=-1.0)

# Transforms
cs.translate([dx, dy])
cs.rotate(degrees)            # single float, rotation about origin
cs.scale([sx, sy])
cs.mirror([nx, ny])
```

---

## 3. Creating Primitives

### 3.1 Box (Rectangular Prism)

```python
from manifold3d import Manifold

# Origin at corner (0,0,0), extends to (W, D, H)
wall = Manifold.cube([20.0, 0.6, 15.0])

# Origin at center
centered_box = Manifold.cube([10.0, 8.0, 12.0], center=True)
```

The `center=True` flag shifts the bounding box to be symmetric about the origin. This is useful for rotation operations. Negative or all-zero dimensions produce an empty Manifold.

**Hotel use case:** Walls, floor slabs, window/door cutout volumes.

### 3.2 Cylinder and Cone

```python
# Cylinder: height along Z, base at z=0
column = Manifold.cylinder(
    height=12.0,
    radius_low=0.4,
    circular_segments=16   # 16 is fine for sub-millimeter columns
)

# Cone: radius_high=0 gives a pointed cone
spire = Manifold.cylinder(height=5.0, radius_low=2.0, radius_high=0.0, circular_segments=24)

# Frustum (truncated cone)
frustum = Manifold.cylinder(height=3.0, radius_low=3.0, radius_high=2.0, circular_segments=24)

# Centered cylinder (origin at midpoint)
centered_cyl = Manifold.cylinder(height=10.0, radius_low=2.0, center=True)
```

**Circular segments rule of thumb for miniature scale:**
- Decorative columns (r < 1mm): 8-12 segments (barely visible)
- Structural cylinders (r 1-3mm): 16-24 segments
- Prominent round features (r > 3mm): 24-32 segments

### 3.3 Sphere

```python
sphere = Manifold.sphere(radius=2.0, circular_segments=24)
```

Internally constructed as a refined octahedron. The segment count is always rounded up to the nearest factor of 4. A sphere of radius 2mm at 24 segments produces ~288 triangles -- adequate for miniature game pieces.

### 3.4 Extrude from CrossSection

This is the most versatile primitive constructor for architectural geometry.

```python
from manifold3d import Manifold, CrossSection

# Simple extrusion of an L-shaped floor plan
floor_plan = CrossSection([
    [[0,0], [12,0], [12,5], [7,5], [7,8], [0,8]]
])
building_shell = Manifold.extrude(floor_plan, height=15.0)

# Extrusion with twist (for decorative towers)
twisted_tower = Manifold.extrude(
    CrossSection.square([4, 4], center=True),
    height=20.0,
    n_divisions=40,       # subdivisions for smooth twist
    twist_degrees=90.0    # quarter-turn over full height
)

# Extrusion with taper (for pyramidal roofs)
roof = Manifold.extrude(
    CrossSection.square([12, 8], center=True),
    height=4.0,
    scale_top=(0.0, 0.0)  # taper to a point = pyramid
)

# Partial taper (hip roof approximation)
hip_roof = Manifold.extrude(
    CrossSection.square([12, 8], center=True),
    height=3.0,
    scale_top=(0.5, 0.3)  # shrink to 50% X, 30% Y at top
)
```

**Coordinate convention:** `extrude()` always extrudes along the **+Z axis**. The CrossSection lies in the XY plane at z=0, and the extruded solid extends from z=0 to z=height.

### 3.5 Revolve from CrossSection

For creating columns, domes, vases, barrel roofs, and other rotational geometry.

```python
from manifold3d import Manifold, CrossSection

# Dome: revolve a quarter-circle profile
import math
n = 16
quarter_circle = [[3.0 * math.cos(i * math.pi / (2*n)),
                    3.0 * math.sin(i * math.pi / (2*n))]
                   for i in range(n + 1)]
quarter_circle.append([0, 3.0])  # close at apex
dome_profile = CrossSection([quarter_circle])
dome = Manifold.revolve(dome_profile, circular_segments=32)

# Barrel roof: revolve only 180 degrees
barrel = Manifold.revolve(dome_profile, circular_segments=24, revolve_degrees=180.0)
```

**Revolve axis convention:** Revolves around the **Y-axis** of the CrossSection, then maps that to the **Z-axis** of the resulting Manifold. The cross-section should be in the **+X** half-plane (positive X side only is used).

### 3.6 Level Set (SDF-based)

For organic shapes that cannot be built from extrusions. Useful for decorative elements.

```python
import math
from manifold3d import Manifold

def rounded_box_sdf(x, y, z):
    """SDF for a box with rounded edges."""
    bx, by, bz = 5.0, 4.0, 6.0  # half-extents
    r = 0.5                        # corner radius
    dx = max(abs(x) - bx + r, 0)
    dy = max(abs(y) - by + r, 0)
    dz = max(abs(z) - bz + r, 0)
    return -(math.sqrt(dx*dx + dy*dy + dz*dz) - r)

rounded = Manifold.level_set(
    rounded_box_sdf,
    [-6, -5, -7, 6, 5, 7],  # [min_x, min_y, min_z, max_x, max_y, max_z]
    0.5                       # approximate edge length in output mesh
)
```

**Performance note:** `level_set` evaluates the SDF at every grid point, making it significantly slower than primitive constructors. Use sparingly; prefer extrude/revolve when possible.

---

## 4. Boolean Operations

### 4.1 Operator Syntax

manifold3d overloads Python operators for natural CSG expressions:

```python
union        = solid_a + solid_b      # OpType.Add
difference   = solid_a - solid_b      # OpType.Subtract
intersection = solid_a ^ solid_b      # OpType.Intersect
```

All boolean operations **guarantee manifold output**. If the inputs are valid Manifolds, the output is always a valid Manifold.

### 4.2 Batch Operations

For combining many solids, `batch_boolean` is preferred over sequential pairwise operations:

```python
from manifold3d import Manifold, OpType

# Union of many parts
parts = [Manifold.cube([2, 2, 2]).translate([i*3, 0, 0]) for i in range(50)]
combined = Manifold.batch_boolean(parts, OpType.Add)

# Subtract: first element is the base, all others are subtracted from it
base = Manifold.cube([20, 20, 5])
holes = [Manifold.cylinder(10, 1.0).translate([2+i*4, 2+j*4, -0.1])
         for i in range(4) for j in range(4)]
result = Manifold.batch_boolean([base] + holes, OpType.Subtract)
```

**Batch subtract semantics:** For `OpType.Subtract`, the **first** element of the list is the "base" and all remaining elements are subtracted from it. This is equivalent to `base - (hole1 + hole2 + ... + holeN)`.

### 4.3 Recommended Two-Phase Boolean Pattern

For building assembly, use a two-phase approach that minimizes the number of boolean operations:

```python
from manifold3d import Manifold, OpType

# Phase 1: Batch-union all cutout volumes into a single solid
window_cutouts = [make_window_cutout(col, floor) for floor in range(5) for col in range(6)]
door_cutouts = [make_door_cutout()]
all_cutouts = Manifold.batch_boolean(window_cutouts + door_cutouts, OpType.Add)

# Phase 2: Single subtract of all cutouts from the shell
building = shell - all_cutouts

# Phase 3: Batch-union all additive features
additive = [roof, *balconies, *window_frames, *cornices]
all_additive = Manifold.batch_boolean(additive, OpType.Add)

# Phase 4: Single union to add features
building = building + all_additive
```

This reduces the CSG tree depth from O(n) to O(1) for n features.

### 4.4 Performance Characteristics

Benchmarked on the test environment (manifold3d 3.3.2):

| Operation | Time | Notes |
|-----------|------|-------|
| 100 non-overlapping box union (batch) | ~0.05ms | Trivial -- no intersection computation |
| 100 non-overlapping box union (sequential) | ~0.08ms | Slightly slower but still fast |
| 50 overlapping sphere union (batch) | ~0.02ms | **3.6x faster** than sequential |
| 50 overlapping sphere union (sequential) | ~0.07ms | Batch wins on overlapping geometry |
| Full hotel (shell + 33 cutouts + roof + slabs) | ~3ms | Realistic workload |

**Key takeaway:** For our hotel workload (dozens of features, not thousands), total CSG time is under 5ms. Performance is not a concern at this scale. The batch approach still matters for code clarity and to avoid accumulating floating-point tolerance issues from deep sequential chains.

---

## 5. Transform Operations

All transforms are **lazy** -- they are accumulated into an affine matrix and applied only when the geometry is actually read (e.g., during a boolean operation or mesh extraction). Chaining transforms has zero cost.

### 5.1 Translate

```python
moved = solid.translate([dx, dy, dz])  # always a 3-element sequence
```

### 5.2 Rotate

```python
rotated = solid.rotate([rx, ry, rz])  # Euler angles in DEGREES, applied X -> Y -> Z
```

Multiples of 90 degrees use optimized code paths that avoid floating-point error entirely. This is important for architectural geometry where walls are axis-aligned.

### 5.3 Scale

```python
scaled = solid.scale([sx, sy, sz])  # per-axis scale factors
```

**Important:** The scalar overload `scale(2.0)` exists in the C++ API but crashes in the Python bindings (manifold3d 3.3.2). Always use the 3-element form:

```python
# DO THIS:
scaled = solid.scale([2.0, 2.0, 2.0])

# NOT THIS (crashes in Python bindings):
# scaled = solid.scale(2.0)
```

### 5.4 Mirror

```python
mirrored = solid.mirror([1, 0, 0])  # mirror across YZ plane (flip X)
mirrored = solid.mirror([0, 1, 0])  # mirror across XZ plane (flip Y)
mirrored = solid.mirror([0, 0, 1])  # mirror across XY plane (flip Z)
```

The argument is the **normal vector** of the mirror plane (passes through origin). Useful for creating symmetric facades: build one half, mirror, union.

### 5.5 General Affine Transform

```python
import math

angle = math.radians(30)
matrix = [
    [math.cos(angle), -math.sin(angle), 0, tx],
    [math.sin(angle),  math.cos(angle), 0, ty],
    [0,                0,                1, tz]
]
transformed = solid.transform(matrix)  # 3x4 matrix: [rotation|translation]
```

The matrix format is 3 rows x 4 columns: the first 3 columns are the 3x3 rotation/scale matrix, and the 4th column is the translation vector.

### 5.6 Chaining

Transforms return new Manifold instances (immutable), enabling fluent chaining:

```python
placed_window = window_frame \
    .rotate([0, 0, 90]) \
    .translate([x, y, z]) \
    .mirror([1, 0, 0])
```

---

## 6. Mesh Extraction

### 6.1 to_mesh() -- For STL Export (Printing)

```python
mesh = solid.to_mesh()

# Vertex positions: float32 numpy array, shape (N, 3+)
vertices = mesh.vert_properties[:, :3]  # first 3 columns are always XYZ

# Triangle indices: int32 numpy array, shape (M, 3)
faces = mesh.tri_verts
```

`to_mesh()` returns a `Mesh` object with shared vertices (each vertex appears once). This ensures the exported mesh is watertight, which is required for 3D printing.

### 6.2 to_mesh() with Normals -- For GLB Export (Web Preview)

For web rendering with smooth/sharp shading, extract normals:

```python
# Step 1: Calculate normals with a sharpness threshold
solid_with_normals = solid.calculate_normals(
    normal_idx=0,       # property channel index where normals start
    min_sharp_angle=50  # edges sharper than 50 degrees get split normals
)

# Step 2: Extract mesh with normals
mesh = solid_with_normals.to_mesh(normal_idx=0)

vertices = mesh.vert_properties[:, :3]    # shape (N, 3), float32
normals  = mesh.vert_properties[:, 3:6]   # shape (N, 3), float32
faces    = mesh.tri_verts                  # shape (M, 3), int32
```

**Important:** When normals are included, vertices at sharp edges are **duplicated** (split) to allow different normals per face. A cube goes from 8 vertices to 24 vertices. This means the mesh is no longer topologically watertight (open edges at the seams), which is expected and correct for rendering purposes.

**Rule:** Use `to_mesh()` (no normals) for STL. Use `calculate_normals()` + `to_mesh(normal_idx=0)` for GLB.

### 6.3 Mesh Object Properties

```python
mesh.vert_properties    # ndarray[float32, (N, num_prop)]  -- vertex data
mesh.tri_verts          # ndarray[int32, (M, 3)]           -- face indices
mesh.run_original_id    # list[int] -- which input mesh each face came from
mesh.run_index          # list[int] -- face index ranges per run
mesh.run_transform      # ndarray[float32, (R, 4, 3)]     -- transforms per run
mesh.face_id            # list[int] -- per-face IDs
mesh.merge_from_vert    # list[int] -- merge vertex mapping (from)
mesh.merge_to_vert      # list[int] -- merge vertex mapping (to)
```

The `run_*` properties enable tracking which faces came from which input Manifold -- useful for applying per-component materials in a renderer.

---

## 7. Integration with trimesh for Export

### 7.1 Manifold to trimesh.Trimesh Conversion

```python
import numpy as np
import trimesh
from manifold3d import Manifold

def manifold_to_trimesh(solid: Manifold) -> trimesh.Trimesh:
    """Convert a Manifold to a trimesh.Trimesh for export."""
    mesh = solid.to_mesh()
    return trimesh.Trimesh(
        vertices=mesh.vert_properties[:, :3],
        faces=mesh.tri_verts
    )
```

### 7.2 STL Export (for 3D Printing)

```python
def export_stl(solid: Manifold, path: str) -> None:
    """Export a Manifold as binary STL."""
    tri = manifold_to_trimesh(solid)
    assert tri.is_watertight, "Mesh must be watertight for 3D printing"
    tri.export(path)  # format inferred from extension

# In-memory export (for HTTP response)
def export_stl_bytes(solid: Manifold) -> bytes:
    """Export a Manifold as binary STL bytes."""
    tri = manifold_to_trimesh(solid)
    return tri.export(file_type='stl')
```

### 7.3 GLB Export (for Web Preview)

```python
def manifold_to_trimesh_with_normals(
    solid: Manifold,
    sharp_angle: float = 50.0
) -> trimesh.Trimesh:
    """Convert a Manifold to trimesh with vertex normals for rendering."""
    solid_n = solid.calculate_normals(0, sharp_angle)
    mesh = solid_n.to_mesh(normal_idx=0)
    return trimesh.Trimesh(
        vertices=mesh.vert_properties[:, :3],
        faces=mesh.tri_verts,
        vertex_normals=mesh.vert_properties[:, 3:6]
    )

def export_glb(solid: Manifold, path: str) -> None:
    """Export a Manifold as GLB for three.js preview."""
    tri = manifold_to_trimesh_with_normals(solid)
    tri.export(path)

def export_glb_bytes(solid: Manifold) -> bytes:
    """Export a Manifold as GLB bytes."""
    tri = manifold_to_trimesh_with_normals(solid)
    return tri.export(file_type='glb')
```

### 7.4 Validation via trimesh

```python
def validate_for_printing(solid: Manifold) -> dict:
    """Run printability checks on a Manifold."""
    tri = manifold_to_trimesh(solid)
    bbox = solid.bounding_box()
    dims = (bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2])
    return {
        'is_watertight': tri.is_watertight,
        'is_volume': tri.is_volume,
        'volume_mm3': tri.volume,
        'euler_number': tri.euler_number,  # should be 2 for a simple solid
        'dimensions_mm': dims,
        'triangle_count': len(tri.faces),
        'manifold_status': str(solid.status()),
    }
```

### 7.5 Typical Output Sizes

For a complete hotel game piece (~15mm tall, 60 windows, roof, slabs):

| Format | Size | Notes |
|--------|------|-------|
| Binary STL | ~40 KB | ~780 triangles |
| GLB | ~14 KB | Compressed, with normals |

Both formats are well within acceptable sizes for web transfer and 3D printer slicers.

---

## 8. Common Pitfalls

### 8.1 Coplanar Faces in Boolean Operations

**The Problem:** When a cutout volume shares an exact face with the target solid, the boolean result is mathematically correct but may produce zero-thickness geometry or faces that confuse some slicers.

**manifold3d handles this correctly** (tested: `Error.NoError` for flush booleans), but best practice is still to overshoot cutout volumes by a small epsilon:

```python
OVERSHOOT = 0.1  # mm

def make_window_cutout(x, y, z, w, h, wall_thickness):
    """Create a window cutout that overshoots both sides of the wall."""
    return Manifold.cube([w, wall_thickness + 2 * OVERSHOOT, h]).translate(
        [x, y - OVERSHOOT, z]
    )
```

This avoids numerical ambiguity and makes the geometry intent explicit.

### 8.2 CrossSection Constructor: List of Contours

`CrossSection()` expects a **list of contours** (list of list of points), not a single contour:

```python
# CORRECT -- list of contours (even for a single contour):
cs = CrossSection([[[0,0], [10,0], [10,10], [0,10]]])

# ALSO CORRECT -- manifold3d auto-wraps a single contour:
cs = CrossSection([[0,0], [10,0], [10,10], [0,10]])

# For a polygon with a hole (outer CCW, hole CW):
cs = CrossSection([
    [[0,0], [10,0], [10,10], [0,10]],      # outer (CCW)
    [[3,3], [3,7], [7,7], [7,3]]            # hole (CW)
])
```

### 8.3 Coordinate System Conventions

| Operation | Axis Convention |
|-----------|----------------|
| `cube()` | Default: origin at (0,0,0), extends to (+X, +Y, +Z) |
| `cylinder()` | Height along **+Z**, base at z=0 |
| `sphere()` | Centered at origin |
| `extrude()` | CrossSection in **XY plane**, extrudes along **+Z** |
| `revolve()` | Revolves around **Y-axis** of CrossSection, maps to **Z-axis** in 3D |
| `rotate()` | Euler angles in **degrees**, applied **X then Y then Z** |

The extrude-along-Z convention means you often need to rotate extruded shapes into position:

```python
# Gable roof profile in XY, extruded along Z, then rotated to sit on top of building
roof_profile = CrossSection([[[0,0], [W,0], [W/2, 3]]])
roof = (Manifold.extrude(roof_profile, D)
        .rotate([90, 0, 0])           # rotate so depth runs along Y
        .translate([0, D, H]))         # position on top of building
```

### 8.4 scale() Python Binding Bug

As of manifold3d 3.3.2, `scale(float)` crashes in the Python bindings despite being documented. Always use the 3-vector form:

```python
# SAFE:
scaled = solid.scale([2.0, 2.0, 2.0])

# CRASHES (Python binding bug):
# scaled = solid.scale(2.0)
```

### 8.5 Zero-Dimension Geometry

```python
Manifold.cube([10, 10, 0])   # NOT empty! Creates a degenerate face. Avoid.
Manifold.cube([-1, 10, 10])  # Empty manifold (negative dimension).
Manifold.cube([0, 0, 0])     # Empty manifold (all zero).
```

Always ensure all dimensions are positive before constructing primitives.

### 8.6 Circular Segment Count vs. Radius

The default circular segment count scales with radius. For miniature game pieces (sub-millimeter features), the default may produce too few segments:

```python
from manifold3d import get_circular_segments

print(get_circular_segments(5.0))   # 32 -- fine
print(get_circular_segments(1.0))   # 8  -- may look faceted
print(get_circular_segments(0.5))   # 4  -- way too few
```

**Solution:** Always pass `circular_segments` explicitly for small features, or set a global minimum:

```python
from manifold3d import set_circular_segments
set_circular_segments(16)  # minimum 16 segments for all circles
```

### 8.7 Empty Manifold Propagation

An empty Manifold (from invalid input or impossible boolean) propagates through all subsequent operations silently. Always check `.status()` and `.is_empty()` after construction:

```python
result = complex_csg_operation()
if result.is_empty():
    print(f"CSG failed: {result.status()}")
```

---

## 9. Performance Tips

### 9.1 Batch Booleans to Minimize Tree Depth

The two-phase pattern (batch all cutouts, then single subtract) is both cleaner and avoids deep CSG trees:

```python
# PREFERRED: flat tree
all_cutouts = Manifold.batch_boolean(cutout_list, OpType.Add)
result = shell - all_cutouts

# AVOID: deep tree (O(n) depth)
result = shell
for cutout in cutout_list:
    result = result - cutout
```

For overlapping geometry, batch_boolean is measurably faster (3-4x for 50 overlapping spheres). For non-overlapping geometry the difference is minimal, but batch is still preferred for code clarity.

### 9.2 Lazy Transforms Are Free

Chaining `.translate().rotate().scale()` costs nothing -- transforms are composed as matrices. The actual vertex transformation happens only during boolean operations or mesh extraction. Feel free to chain as many transforms as needed.

### 9.3 Reuse Geometry via compose()

If you have identical features placed in multiple locations, create the geometry once and compose:

```python
# Create window frame once
frame = make_window_frame(1.2, 1.5, 0.1)

# Place many copies (transforms are lazy)
frames = [frame.translate([x, y, z]) for x, y, z in window_positions]

# Compose if non-overlapping (O(1), just concatenates vertex buffers)
all_frames = Manifold.compose(frames)

# Or batch_boolean if they might overlap
all_frames = Manifold.batch_boolean(frames, OpType.Add)
```

`compose()` is O(1) but requires that the input manifolds do not overlap. It simply concatenates vertex buffers without any boolean computation.

### 9.4 Minimize Boolean Operand Complexity

Simpler operands make booleans faster. When creating cutout volumes, use the simplest possible geometry:

```python
# GOOD: box cutout (12 triangles)
cutout = Manifold.cube([w, thickness + 0.2, h])

# UNNECESSARY: high-res cylinder cutout (640 triangles) for a rectangular window
# cutout = Manifold.cylinder(h, w/2, circular_segments=64)
```

### 9.5 Use as_original() to Enable Simplification

After complex boolean chains, face boundaries from different input meshes prevent triangle merging. Calling `.as_original()` resets the provenance tracking and allows `.simplify()` to reduce triangle count:

```python
result = complex_boolean_chain()
simplified = result.as_original().simplify()
print(f"Reduced from {result.num_tri()} to {simplified.num_tri()} triangles")
```

---

## 10. Limitations and Workarounds

### 10.1 No Fillets or Chamfers

manifold3d has no built-in fillet or chamfer operations. This is the most significant limitation compared to BREP kernels like OpenCascade.

**Workaround A: CrossSection offset for 2D rounded corners**

The most practical approach for architectural geometry. Shrink then expand a profile to round its corners:

```python
from manifold3d import CrossSection, JoinType

def rounded_rectangle(w, h, radius, segments=16):
    """Create a rectangle with rounded corners."""
    rect = CrossSection.square([w, h], center=True)
    return (rect
            .offset(-radius, join_type=JoinType.Round, circular_segments=segments)
            .offset(radius, join_type=JoinType.Round, circular_segments=segments))

# Extrude for a rounded-corner prism (rounded in XY, sharp in Z)
profile = rounded_rectangle(10, 8, 0.5)
rounded_box = Manifold.extrude(profile, 12.0)
```

This gives rounded corners in the XY plane. The Z edges remain sharp. For miniature game pieces (~1-2cm), this is usually sufficient since the Z-edges are too small to catch on fingers anyway.

**Workaround B: Hull-based chamfer**

Use the convex hull of two slightly different-sized shapes to create 45-degree chamfers:

```python
from manifold3d import Manifold

def chamfered_box(w, d, h, chamfer):
    """Box with chamfered edges via hull."""
    inner = Manifold.cube([w - 2*chamfer, d - 2*chamfer, h], center=True)
    outer = Manifold.cube([w, d, h - 2*chamfer], center=True)
    return Manifold.batch_hull([inner, outer])
```

This produces a box with 45-degree chamfers on all 4 vertical edges and top/bottom edges. Triangle count is low (28 vs 12 for a plain box).

**Workaround C: smooth() + refine() for organic rounding**

Applies cubic spline interpolation to mesh edges. Creates a "blobby" rounded version:

```python
mesh = Manifold.cube([10, 10, 10], center=True).to_mesh()
rounded = Manifold.smooth(mesh).refine(4)
```

**Warning:** This dramatically inflates volume (a 10x10x10 cube becomes ~2647mm^3 instead of 1000mm^3) because it rounds everything uniformly. Not suitable for architectural geometry. Only useful for decorative organic elements.

**Workaround D: SDF via level_set() for true 3D rounding**

For features that genuinely need rounded 3D edges (e.g., a smooth dome cap):

```python
import math
from manifold3d import Manifold

def rounded_box_sdf(x, y, z):
    bx, by, bz, r = 5.0, 4.0, 6.0, 0.5
    dx = max(abs(x) - bx + r, 0)
    dy = max(abs(y) - by + r, 0)
    dz = max(abs(z) - bz + r, 0)
    return -(math.sqrt(dx*dx + dy*dy + dz*dz) - r)

rounded = Manifold.level_set(rounded_box_sdf, [-6,-5,-7, 6,5,7], 0.3)
```

This produces a true rounded box but at significantly higher triangle count (~6000 vs 12) and computation cost. Use only for hero features, not bulk geometry.

**Recommendation for our project:** Use Workaround A (CrossSection offset) for floor plan profiles and Workaround B (hull chamfer) for decorative elements. At miniature scale (1-2cm total height, feature sizes under 1mm), rounded edges are barely visible and not worth the triangle count overhead of Workarounds C/D.

### 10.2 No NURBS or Spline Surfaces

manifold3d works exclusively with triangle meshes. There are no spline surfaces, Bezier patches, or NURBS.

**Workaround:** Approximate curves with polylines in `CrossSection`, then extrude. For a game piece at 1-2cm scale, a circle with 16-24 segments is indistinguishable from a true circle.

### 10.3 No Direct Minkowski Sum/Offset in 3D

There is no 3D offset/shell operation (Minkowski sum with a sphere). The hollow shell must be built manually:

```python
# Manual shell: subtract a slightly smaller solid
outer = Manifold.cube([W, D, H])
inner = Manifold.cube([W - 2*t, D - 2*t, H - t]).translate([t, t, t])
shell = outer - inner
```

### 10.4 No Text/Engraving Primitives

No built-in text rendering. For embossed text on game pieces, generate text outlines externally (e.g., via Pillow/FreeType), convert to `CrossSection`, and extrude:

```python
# Hypothetical workflow (text outline generation is external):
text_polygons = generate_text_outlines("HOTEL", font_size=2.0)
text_cs = CrossSection(text_polygons)
text_solid = Manifold.extrude(text_cs, 0.3)  # 0.3mm emboss depth
building = building + text_solid.translate([x, y, z])
```

### 10.5 No Undo / Mutability

All Manifold operations return new instances. There is no undo or in-place modification. This is actually a benefit for our pipeline -- it makes the CSG tree purely functional and easy to reason about.

---

## 11. Verdict

**manifold3d is an excellent fit for this project.** Key reasons:

1. **Guaranteed watertight output** eliminates an entire class of 3D printing failures.
2. **Sub-5ms total CSG time** for a complete hotel model -- fast enough for interactive preview.
3. **Tiny dependency footprint** (~1.2 MB wheel) keeps deployment simple.
4. **Clean Python API** with operator overloading (`+`, `-`, `^`) makes CSG expressions readable.
5. **Lazy transforms** enable fluent chaining without performance cost.
6. **No fillet limitation is acceptable** at miniature game-piece scale -- CrossSection offset handles the cases where rounding matters.

The main risks are:

- The `scale(float)` Python binding bug is minor (workaround: use 3-vector form).
- No 3D offset means hollow shells require manual construction (straightforward for box-like buildings).
- `level_set` is slow for complex SDFs, but we should rarely need it.

**Recommended global setup for our project:**

```python
from manifold3d import set_circular_segments

# Ensure even small-radius circles get enough segments for clean prints
set_circular_segments(16)
```

**Recommended conversion utilities:**

```python
from manifold3d import Manifold
import trimesh
import numpy as np


def manifold_to_trimesh(solid: Manifold) -> trimesh.Trimesh:
    """Convert Manifold to trimesh for STL export (shared vertices, watertight)."""
    mesh = solid.to_mesh()
    return trimesh.Trimesh(
        vertices=mesh.vert_properties[:, :3],
        faces=mesh.tri_verts
    )


def manifold_to_trimesh_glb(solid: Manifold, sharp_angle: float = 50.0) -> trimesh.Trimesh:
    """Convert Manifold to trimesh for GLB export (split vertices with normals)."""
    solid_n = solid.calculate_normals(0, sharp_angle)
    mesh = solid_n.to_mesh(normal_idx=0)
    return trimesh.Trimesh(
        vertices=mesh.vert_properties[:, :3],
        faces=mesh.tri_verts,
        vertex_normals=mesh.vert_properties[:, 3:6]
    )
```

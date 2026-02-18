# 3D Printing Constraints for Miniature Hotel Game Pieces

> Expert reference for the procedural geometry engine. All values are in millimeters
> unless stated otherwise. Target piece size: 10-20mm tall (Monopoly-scale).

---

## Table of Contents

1. [FDM vs Resin Printing Constraints](#1-fdm-vs-resin-printing-constraints)
2. [Minimum Dimensions for Architectural Features](#2-minimum-dimensions-for-architectural-features)
3. [STL Mesh Requirements](#3-stl-mesh-requirements)
4. [Orientation and Support Considerations](#4-orientation-and-support-considerations)
5. [Common Failure Modes and Design Mitigations](#5-common-failure-modes-and-design-mitigations)
6. [Tolerances and Overshoot Values for Boolean Operations](#6-tolerances-and-overshoot-values-for-boolean-operations)
7. [Surface Detail Limits](#7-surface-detail-limits)
8. [Quick-Reference Tables for the Generator](#8-quick-reference-tables-for-the-generator)

---

## 1. FDM vs Resin Printing Constraints

### 1.1 Fundamental Resolution Limits

FDM (Fused Deposition Modeling) and resin (SLA/MSLA/DLP) printers differ dramatically
in what they can resolve at the 10-20mm scale. The generator must treat these as two
distinct constraint profiles.

| Parameter | FDM (0.4mm nozzle) | FDM (0.2mm nozzle) | Resin (MSLA ~50um XY) |
|---|---|---|---|
| XY resolution (practical) | 0.4-0.5mm | 0.2-0.3mm | 0.05-0.10mm |
| Z layer height (typical) | 0.10-0.20mm | 0.05-0.12mm | 0.025-0.050mm |
| Min wall thickness (single pass) | 0.4mm (fragile) | 0.2mm (fragile) | 0.3mm (structural) |
| Min wall thickness (robust) | 0.8mm (2 perimeters) | 0.5mm | 0.5mm |
| Min positive feature width | 0.6mm | 0.3mm | 0.2mm |
| Min hole/slot width | 0.6mm | 0.3mm | 0.3mm (resin trapping risk below) |
| Min embossed/engraved line | 0.4mm wide, 0.2mm deep | 0.2mm wide, 0.1mm deep | 0.15mm wide, 0.10mm deep |

### 1.2 Wall Thickness

Wall thickness is the single most critical parameter for miniatures.

**FDM (standard 0.4mm nozzle):**
- Absolute minimum: 0.4mm (single extrusion width). This is structurally weak and
  prone to delamination. Not recommended for any load-bearing geometry.
- Practical minimum: 0.8mm (2 perimeters). This is the recommended floor for all
  exterior walls of the hotel body.
- Robust: 1.2mm (3 perimeters). Use for the base/foundation of the piece, which
  must survive handling.

**Resin:**
- Absolute minimum: 0.3mm. Printable but extremely fragile; will snap under finger
  pressure at this scale.
- Practical minimum: 0.5mm. Adequate for decorative features that do not bear load.
- Robust: 0.8mm. Use for the main building shell and base.

**Generator rule:** The main body walls should never go below 0.8mm (FDM) or 0.5mm
(resin). Decorative sub-features like window frames may go to 0.6mm (FDM) or 0.3mm
(resin), but only when backed by or connected to thicker geometry.

### 1.3 Overhangs

Overhangs are surfaces that extend outward without support from below. The overhang
angle is measured from the vertical axis (0 degrees = straight vertical wall,
90 degrees = perfectly horizontal ceiling).

**FDM:**
- Safe without supports: up to 45 degrees from vertical (i.e., the classic 45-degree
  rule). Many printers can push to 50-55 degrees with good cooling.
- 60-70 degrees: prints with visible surface degradation (drooping, rough underside).
- 90 degrees (horizontal ceiling): requires supports or bridging.

**Resin:**
- Safe without supports: up to 60 degrees on most machines (resin printers print
  inverted, so "overhangs" behave differently).
- Flat horizontal surfaces perpendicular to the build plate can cause suction-cup
  effects during peel; hollowing or drainage holes help but are generally not
  relevant for solid miniatures this small.

**Generator rule:** All overhangs in the generated geometry should stay at or below
45 degrees for FDM compatibility. Roof slopes, canopies, balcony undersides, and
any protruding elements must respect this. For resin-only output, this can be
relaxed to 55 degrees.

### 1.4 Bridging

Bridging is unsupported horizontal spans between two vertical supports (e.g., a
lintel over a window, or the ceiling of a recessed door).

**FDM:**
- Reliable bridging distance: up to 5-6mm with good cooling.
- At miniature scale (windows ~1-2mm wide), bridging is generally not a concern
  because span lengths are tiny. A 1.5mm window opening will bridge fine.
- Bridges longer than 10mm will sag visibly.

**Resin:**
- Bridging is not a meaningful concept in resin printing (each layer is fully cured
  before the next), so horizontal spans of any size within the XY plane are fine.

**Generator rule:** For FDM, avoid horizontal spans wider than 6mm without
intermediate support geometry. At miniature scale, this constraint is rarely
triggered since most features are under 3mm wide.

### 1.5 Layer-Dependent Detail

Because FDM builds in layers (typically 0.1-0.2mm), features in the Z direction are
quantized. A roof slope that rises 0.5mm over 2mm of horizontal run will consist of
only 2-5 stair-stepped layers. This is generally acceptable for miniatures where
viewers expect a stylized look.

Resin at 0.025-0.05mm layers gives 10-20x finer Z resolution. Sloped surfaces will
appear much smoother.

---

## 2. Minimum Dimensions for Architectural Features

At 10-20mm total height, architectural features must be abstracted. The following
table gives the minimum size at which a feature is both printable and visually
recognizable as what it represents.

### 2.1 Master Feature Size Table

| Feature | Min Width | Min Height | Min Depth/Protrusion | Notes |
|---|---|---|---|---|
| **Window (cutout)** | 0.8mm FDM / 0.5mm resin | 0.8mm FDM / 0.5mm resin | through-wall or 0.3mm recess | Rectangular cutouts are simplest and most reliable |
| **Window (frame)** | 0.6mm frame width FDM / 0.3mm resin | same as opening | 0.2mm proud of wall FDM / 0.15mm resin | Frame adds recognizability but increases mesh complexity |
| **Door (cutout)** | 1.0mm | 1.5mm | through-wall or 0.4mm recess | Must be visibly taller than windows |
| **Door canopy** | 1.2mm wide | 0.3mm thick | 0.5mm protrusion | 45-degree underside slope for FDM |
| **Column (round)** | 0.8mm diameter FDM / 0.4mm resin | free-standing max 4mm | N/A | FDM cylinders below 0.8mm collapse; resin below 0.4mm snap |
| **Column (square)** | 0.6mm x 0.6mm FDM / 0.4mm resin | free-standing max 4mm | N/A | Square columns print better than round on FDM |
| **Balcony slab** | 1.0mm deep | 0.4mm thick FDM / 0.3mm resin | 0.5-1.0mm protrusion from wall | Must be supported from below or self-supporting at 45 degrees |
| **Balcony railing** | N/A | 0.5mm FDM / 0.3mm resin | 0.4mm wide FDM / 0.2mm resin | Consider solid railing wall instead of individual balusters |
| **Railing balusters** | 0.6mm spacing | 0.8mm tall | 0.5mm thick | FDM only; resin can go 0.3mm thick |
| **Flat roof parapet** | wall width (0.8mm+) | 0.5mm min | wall width | Easy to print; just an extension of the wall |
| **Gabled roof** | building width | min 1.5mm rise | N/A | Slope must be >= 20 degrees to read visually as a gable |
| **Hipped roof** | building width | min 1.5mm rise | N/A | Four slopes; all slopes must meet cleanly at ridgeline |
| **Mansard roof** | building width | min 2.0mm rise | N/A | Two-stage slope: steep lower (~70deg), shallow upper (~20deg) |
| **Barrel/tile roof** | building width | 1.0mm min rise | N/A | Simplified to smooth cylinder section at this scale |
| **Dormer window** | 1.0mm wide | 1.0mm tall | 0.5mm protrusion from roof slope | FDM: very difficult below these sizes; resin-only feature |
| **Turret (round)** | 1.5mm diameter | 3-6mm | conical or domed cap 0.5mm | FDM: min 2.0mm diameter recommended |
| **Bay window** | 1.5mm wide | 1.5mm tall | 0.5mm protrusion | Angled sides at 30-45 degrees from wall |
| **Floor band/stringcourse** | building width | 0.3mm tall | 0.2mm protrusion | Subtle but effective horizontal line |
| **Cornice** | building width | 0.4mm tall | 0.3-0.5mm protrusion | Must have 45-degree undercut or chamfer for FDM |
| **Pediment (triangular)** | facade width | 1.0mm rise | 0.3mm protrusion | Simple extruded triangle; below 0.8mm rise it vanishes |
| **Vertical fins (Art Deco)** | 0.5mm thick FDM / 0.3mm resin | 2-6mm tall | 0.3mm protrusion | Prone to breaking; consider thickening for FDM |
| **Stoop/steps** | 1.0mm wide | 0.3mm per step | 0.5mm per step depth | 2-3 steps max; each step is one FDM layer at 0.3mm height |
| **Arched window** | 0.8mm wide | 1.0mm tall | through-wall | Arch is approximated with 6-8 segments minimum |
| **Pilaster** | 0.5mm wide | floor height | 0.3mm protrusion | Rectangular column attached to wall |

### 2.2 Feature Scaling Philosophy

At 1:1000 to 1:2000 scale (roughly what 15mm represents for a 15-30m building),
almost all features are symbolic rather than literal. The goal is:

- **Silhouette recognition:** Roofline shape, overall massing, and proportions carry
  most of the style identity. These are free in terms of printing difficulty.
- **Medium-detail cues:** Windows as recesses or cutouts, doors as taller recesses,
  floor bands, cornices. These are achievable on both FDM and resin.
- **Fine detail:** Window muntins, ornamental moldings, individual roof tiles,
  railing balusters. These are resin-only at best, and often below printable
  resolution. The generator should omit or greatly simplify these.

**Generator rule:** Never generate features smaller than the printer profile's minimum
feature size. Use the printer profile to decide whether to include optional detail
features (e.g., window frames, individual balusters vs. solid railing walls).

---

## 3. STL Mesh Requirements

### 3.1 Watertight / Manifold Geometry

The generated STL **must** be watertight (also called "manifold" or "2-manifold").
This means:

- Every edge is shared by exactly two triangles.
- No holes, gaps, or missing faces anywhere in the mesh.
- All face normals point outward consistently (no inverted normals).
- No self-intersections (triangles passing through other triangles in the same mesh).
- No zero-thickness geometry (knife-edges, single-face walls, degenerate triangles).
- The mesh encloses a non-zero volume.

**Why this matters:** Slicers (Cura, PrusaSlicer, ChiTuBox) will either refuse to
slice a non-manifold mesh or will produce unpredictable results (missing layers,
inverted infill, holes in the print).

Since the project uses **manifold3d** as the CSG engine, watertightness is
guaranteed by construction as long as:

1. All input primitives are valid manifolds (boxes, cylinders, extruded closed
   polygons).
2. Boolean operations are performed via the manifold3d API (which maintains the
   manifold invariant).
3. No post-processing step breaks the mesh (e.g., naively deleting faces or
   vertices in trimesh).

**Generator rule:** Never manipulate individual vertices/faces after CSG operations.
Use manifold3d for all geometric operations. Only use trimesh for export (converting
to STL/GLB) and read-only validation checks.

### 3.2 Triangle Count and Mesh Density

At 10-20mm scale, the mesh does not need to be extremely dense, but curved surfaces
need enough triangles to avoid visible faceting.

**Cylinder/circle segment counts:**

| Feature Diameter | FDM Segments | Resin Segments | Rationale |
|---|---|---|---|
| < 1.0mm | 8 | 12 | Below nozzle resolution anyway on FDM |
| 1.0-2.0mm | 12 | 16 | Facets smaller than layer width |
| 2.0-4.0mm | 16 | 24 | Good visual quality |
| 4.0-8.0mm | 24 | 32 | Smooth to the eye |
| > 8.0mm (rare at this scale) | 32 | 48 | Overkill for miniatures but harmless |

**Formula for the generator:**
```
segments = max(8, min(48, round(diameter_mm * 8)))
```
This gives ~8 segments per millimeter of diameter, clamped to [8, 48]. For resin,
multiply by 1.5:
```
segments_resin = max(12, min(64, round(diameter_mm * 12)))
```

**Total triangle count guidelines:**
- A simple hotel (box + flat roof + windows): 500-2,000 triangles.
- A complex hotel (turrets, bay windows, columns, mansard roof): 5,000-20,000
  triangles.
- Upper soft limit: 50,000 triangles. Beyond this, slicer performance degrades for
  no visual benefit at this scale.
- Upper hard limit: 200,000 triangles. This would indicate a bug (e.g., unmerged
  duplicate geometry or excessive cylinder segments).

**Generator rule:** Use the segment-count formula above for all cylinders and arcs.
After final assembly, log the triangle count. Warn if it exceeds 50,000.

### 3.3 Triangle Quality

Degenerate triangles cause slicer issues. Avoid:

- **Zero-area triangles** (all three vertices collinear or coincident). manifold3d
  should not produce these, but verify after trimesh conversion.
- **Extremely thin triangles** (aspect ratio > 100:1). These can cause numerical
  issues in slicers. Not usually a problem with CSG-generated meshes.
- **Duplicate triangles** (same three vertices appearing twice). Can happen if
  geometry is unioned with itself.

The trimesh library provides `trimesh.Trimesh.is_watertight` and
`trimesh.Trimesh.is_volume` checks. Use both in the validation step.

### 3.4 STL File Format

- Export as **binary STL** (not ASCII). Binary is 5-10x smaller and loads faster.
- Coordinate units: **millimeters**. This is the de facto standard for STL files
  intended for 3D printing. Slicers assume mm unless told otherwise.
- Origin convention: Place the model so that the **bottom of the base sits at Z=0**.
  The model should rest flat on the XY plane with no geometry below Z=0.
- Centering: Center the model on the XY origin (0,0) for convenience, though this is
  not strictly required.

---

## 4. Orientation and Support Considerations

### 4.1 Intended Print Orientation

The generated hotel pieces are designed to be printed **upright** (base on the build
plate, roof pointing up). This is the natural orientation and avoids needing supports
for most geometry.

**Design for upright printing means:**
- The base must be flat (Z=0 plane) with a large footprint for bed adhesion.
- All overhangs should face upward (roof eaves, balconies, canopies).
- Window recesses should be in vertical walls (self-supporting).
- No geometry should protrude below the base.

### 4.2 Base Design

The base is critical for both printing and gameplay. Recommended dimensions:

- **Base footprint:** At least 8mm x 8mm, preferably 10mm x 10mm or larger. A
  Monopoly hotel sits on a property space roughly 15mm wide.
- **Base thickness:** 1.0-1.5mm. This provides:
  - Enough material for solid bed adhesion on FDM.
  - A stable, flat bottom for the game piece to stand on.
  - A visual "foundation" that reads as a building platform.
- **Base chamfer/bevel:** Add a 0.3mm x 45-degree chamfer on the bottom edge to
  compensate for elephant's foot (first-layer squish on FDM). Alternatively, accept
  a slight elephant's foot as it helps adhesion.

### 4.3 Overhang Management

Elements that create overhangs and how to handle them:

| Element | Overhang Risk | Mitigation |
|---|---|---|
| Flat roof overhang/eave | Horizontal = 90 deg | Limit protrusion to 0.5mm, or add 45-degree chamfer underneath |
| Balcony underside | 90 degrees | Add 45-degree support wedge underneath, or make balcony thin enough to bridge (< 2mm protrusion) |
| Door canopy | 90 degrees | Wedge-shaped profile: 45 deg minimum slope on underside |
| Gabled roof soffit | Varies | Keep roof slope >= 30 degrees; soffit is then self-supporting |
| Cornice | Nearly 90 deg | Make it a 45-degree chamfer profile, not a sharp horizontal shelf |
| Bay window underside | 90 degrees | 45-degree bracket underneath, or ramp the underside |
| Turret cap | Conical, usually safe | Keep cone half-angle <= 45 degrees from vertical |
| Arched window top | Curved overhang | Arches are self-supporting if the arch spans < 3mm; above that, flatten the top to a lintel |

**Generator rule:** Every horizontal protrusion (balcony, canopy, cornice, eave)
must either:
1. Protrude less than 0.5mm (bridgeable on FDM), OR
2. Have a 45-degree chamfer or wedge on its underside, OR
3. Be flagged as resin-only geometry.

### 4.4 Support-Free Design Goal

The generator should aim to produce models that require **zero supports**. This
means:

- No floating geometry (everything connects to the main body).
- No overhangs exceeding 45 degrees (FDM) or 55 degrees (resin).
- No enclosed cavities that trap support material.
- No geometry that bridges gaps wider than 5mm.

If a style requires geometry that violates these rules (e.g., a deep balcony, a
large canopy), the FDM profile should automatically add structural support geometry
as part of the model itself (e.g., brackets, columns, wedge fills).

---

## 5. Common Failure Modes and Design Mitigations

### 5.1 Thin Features Breaking Off

**Problem:** Columns, railings, fins, and other thin protrusions snap during
printing, removal from the build plate, or handling.

**Mitigation:**
- Enforce minimum cross-section: 0.8mm x 0.8mm for FDM, 0.4mm x 0.4mm for resin.
- Add fillets at the base of thin protrusions (0.2-0.3mm radius). Even a small
  fillet dramatically increases the stress resistance at the joint.
- Limit the aspect ratio of thin features to 6:1 (height:width). A 0.8mm column
  should not exceed ~5mm in height.
- For FDM, prefer square cross-sections over round (square columns print more
  reliably than round at small diameters).

### 5.2 Small Features Not Printing at All

**Problem:** Features smaller than the printer's resolution simply do not appear in
the print, or appear as vague bumps.

**Mitigation:**
- Check every feature against the printer profile's minimum feature size before
  generating it. If below threshold, either omit it or enlarge it to the minimum.
- Window frames below 0.6mm (FDM) will not be visible; skip the frame and use a
  simple cutout.
- Engraved lines below 0.4mm wide / 0.2mm deep (FDM) will not print; skip them.

### 5.3 Stringing and Blobbing on Fine Detail

**Problem:** FDM printers leave strings and blobs when the nozzle travels between
small features (e.g., a row of small windows with gaps between them).

**Mitigation:**
- This is a slicer/printer tuning issue, not a geometry issue, but the geometry can
  help by avoiding isolated tiny features that require many travel moves.
- Prefer continuous geometry: a row of windows as cutouts from a solid wall, rather
  than individual window frames as separate raised features.
- Minimize the number of disconnected positive features at the same Z height.

### 5.4 Elephant's Foot on First Layer

**Problem:** FDM first layers are squished slightly, causing the base to flare out
by 0.1-0.3mm.

**Mitigation:**
- Add a 0.3mm x 45-degree chamfer on the bottom edge of the base.
- Alternatively, accept it; for game pieces, a slightly wider base improves stability.

### 5.5 Warping and Lifting

**Problem:** Large flat bases can warp on FDM (especially ABS/ASA; less so with PLA).

**Mitigation:**
- At miniature scale (base < 20mm x 20mm), warping is minimal with PLA.
- The base is small enough that a brim (added in the slicer) handles adhesion.
- No geometry-level mitigation needed from the generator.

### 5.6 Resin Suction / Peel Forces

**Problem:** Large flat horizontal cross-sections in resin printing create suction
during the peel step, potentially tearing the print off the build plate.

**Mitigation:**
- At miniature scale, the cross-sectional area is small (< 400mm^2), so peel forces
  are low.
- If the building has a large flat roof parallel to the build plate, this is the
  largest cross-section. At 15mm x 10mm = 150mm^2, this is well within safe limits.
- No geometry-level mitigation needed for pieces this small.

### 5.7 Non-Manifold Edges from Boolean Operations

**Problem:** Boolean operations can produce zero-thickness walls, edges shared by
more than two faces, or other non-manifold artifacts when operands are exactly
tangent or coplanar.

**Mitigation:**
- Overshoot all boolean cutouts by 0.1mm (see Section 6).
- Never place two surfaces exactly coplanar (offset by at least 0.01mm).
- Use manifold3d, which handles edge cases robustly and guarantees manifold output.

### 5.8 Z-Fighting and Coplanar Faces

**Problem:** When two faces occupy the exact same plane, the boolean engine may
produce degenerate geometry or unpredictable results.

**Mitigation:**
- Offset all touching geometry by at least 0.01mm.
- Cutout volumes should extend 0.1mm beyond the surface they cut.
- Additive features (frames, cornices) should be embedded 0.05-0.1mm into the wall
  they attach to, ensuring a solid overlap rather than a flush joint.

---

## 6. Tolerances and Overshoot Values for Boolean Operations

### 6.1 The Coplanar Face Problem

When a subtracted volume's face is exactly coplanar with the target's face, the
boolean engine faces an ambiguous situation: should the shared face belong to the
result or be removed? Different engines handle this differently, and even robust
engines like manifold3d can produce zero-thickness shells or other artifacts.

**Solution:** Always extend boolean operands past the boundary they are cutting.

### 6.2 Recommended Overshoot Values

| Operation | Overshoot Distance | Direction | Example |
|---|---|---|---|
| Window cutout through wall | 0.1mm | Both sides of the wall | Cutout box is wall_thickness + 0.2mm deep |
| Door cutout through wall | 0.1mm | Both sides of wall | Same as window |
| Window recess (not through) | 0.1mm | Outer face only | Recess box starts 0.1mm outside the wall surface |
| Roof trim (cutting top of walls) | 0.1mm | Downward into wall | Roof cut volume extends 0.1mm below the theoretical cut line |
| Floor slab groove | 0.1mm | Outward through wall face | Groove extends 0.1mm beyond outer wall surface |
| Any subtraction from any surface | 0.1mm | Through the surface being cut | Universal rule |

### 6.3 Embedding Overshoot for Unions

When adding geometry to a surface (e.g., a window frame onto a wall, a column
against a wall, a cornice onto a facade), the added geometry must **overlap** with
the target, not merely touch it.

| Operation | Overlap Distance | Rationale |
|---|---|---|
| Frame onto wall surface | 0.05-0.1mm embedded into wall | Ensures solid connection; no zero-thickness boundary |
| Column against wall | 0.1mm embedded into wall | Prevents a hairline gap at the contact plane |
| Balcony slab from wall | 0.1mm embedded into wall | Same |
| Roof onto walls | 0.1mm overlap with wall tops | Prevents gap between roof and wall |
| Base/foundation under walls | 0.1mm overlap | Walls extend 0.1mm into the base slab |

### 6.4 Numerical Precision

- Use `float64` (double precision) for all coordinate calculations. At millimeter
  scale, float32 gives ~6 decimal digits, which is sufficient, but float64 avoids
  accumulation errors in complex CSG trees.
- Round final coordinates to 4 decimal places (0.0001mm = 0.1 micron) before export.
  This is far below any printer's resolution and avoids floating-point noise in the
  STL file.
- manifold3d internally uses double precision, so this is handled automatically.

### 6.5 Summary Constants for the Generator

```python
# Boolean operation constants (mm)
BOOLEAN_OVERSHOOT = 0.1       # Extend subtractions past the target surface
BOOLEAN_EMBED = 0.1           # Embed additive features into the target surface
COPLANAR_OFFSET = 0.01        # Minimum offset to avoid coplanar faces
MIN_WALL_CLEARANCE = 0.01     # Minimum gap between non-intersecting geometry
COORDINATE_PRECISION = 4      # Decimal places for rounding final coordinates
```

---

## 7. Surface Detail Limits

### 7.1 What Is Achievable

The following details are reliably printable at 10-20mm miniature scale:

**On both FDM and Resin:**
- Rectangular window and door cutouts (recessed or through-wall)
- Floor bands / stringcourses (horizontal lines 0.3mm+ tall, 0.2mm+ protrusion)
- Roof shapes (gabled, hipped, flat with parapet, mansard)
- Stepped massing (Art Deco setbacks, L-shaped plans)
- Cornices with 45-degree chamfer profiles
- Square columns / pilasters (0.8mm+ FDM, 0.4mm+ resin)
- Solid balcony railings (not individual balusters on FDM)
- Base with simple chamfer

**On Resin only:**
- Arched window tops with smooth curves
- Round columns down to 0.4mm diameter
- Individual railing balusters (0.3mm thick, 0.3mm spacing)
- Window frames (0.3mm wide raised border)
- Fine engraved lines (0.15mm wide, 0.1mm deep)
- Dormers on roof slopes
- Ornamental detail on pediments or crowns

### 7.2 What Is NOT Achievable (Even on Resin)

These features are below the resolution of any consumer printer at this scale and
should not be attempted:

- Individual window panes / muntins (would need 0.1mm bars)
- Ornamental ironwork patterns
- Text / signage (legible text at this scale would need ~0.05mm stroke width)
- Individual roof tiles / shingles (each tile would be ~0.1mm)
- Door handles, hinges, or hardware
- Window shutters as separate thin panels
- Brickwork texture (individual bricks would be ~0.05mm)
- Any surface texture with features below 0.15mm

### 7.3 Engraved vs Embossed Detail

For surface detail that sits at the boundary of printability:

**Engraved (recessed into surface):**
- Easier to print on FDM because no overhang is created.
- Minimum groove width: 0.4mm FDM / 0.2mm resin.
- Minimum groove depth: 0.2mm FDM / 0.1mm resin.
- Use for: floor lines, window grid patterns, door panels.

**Embossed (raised from surface):**
- Harder on FDM because narrow raised features may not bond well.
- Minimum raised width: 0.5mm FDM / 0.2mm resin.
- Minimum raised height: 0.2mm FDM / 0.1mm resin.
- Use for: window frames, pilasters, cornices, stringcourses.

**Generator rule:** When the printer profile is FDM, prefer engraved detail over
embossed where either would achieve the desired visual effect. When the profile is
resin, both are equally viable.

### 7.4 Detail Budget by Style

Not all styles need fine detail. The generator should adjust detail density based
on the style:

| Style | Required Detail Level | Key Features to Prioritize |
|---|---|---|
| Modern | Low | Clean surfaces, window grid pattern, roof edge |
| Skyscraper | Low | Height proportions, crown shape, floor bands |
| Art Deco | Medium | Stepped massing, vertical fins, crown geometry |
| Classical | Medium | Columns/pilasters, pediment triangle, cornice |
| Mediterranean | Medium | Roof shape, arched windows (resin) or rectangular (FDM), thick walls |
| Townhouse | Medium | Mansard roof profile, stoop steps, bay window |
| Tropical | Medium | Deep overhangs, stilt columns, multi-tier roof |
| Victorian | High | Turret, asymmetric massing, bay window, complex roofline |

---

## 8. Quick-Reference Tables for the Generator

### 8.1 Printer Profile Constants

```python
FDM_PROFILE = {
    "min_wall_thickness": 0.8,       # mm
    "min_feature_size": 0.6,         # mm, smallest positive feature
    "min_hole_size": 0.6,            # mm, smallest cutout dimension
    "min_column_diameter": 0.8,      # mm, round columns
    "min_column_width": 0.6,         # mm, square columns
    "min_emboss_width": 0.5,         # mm
    "min_emboss_height": 0.2,        # mm
    "min_engrave_width": 0.4,        # mm
    "min_engrave_depth": 0.2,        # mm
    "max_overhang_angle": 45,        # degrees from vertical
    "max_bridge_span": 6.0,          # mm
    "max_aspect_ratio": 6,           # height:width for thin features
    "base_thickness": 1.2,           # mm
    "base_chamfer": 0.3,             # mm
    "cylinder_segments_per_mm": 8,   # segment count = diameter * this
    "min_cylinder_segments": 8,
    "max_cylinder_segments": 48,
    "use_window_frames": False,      # Too small for FDM at this scale
    "use_individual_balusters": False,
    "use_arched_windows": False,     # Use rectangular instead
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
    "max_aspect_ratio": 10,          # height:width for thin features
    "base_thickness": 1.0,           # mm
    "base_chamfer": 0.2,             # mm
    "cylinder_segments_per_mm": 12,  # Higher for smoother curves
    "min_cylinder_segments": 12,
    "max_cylinder_segments": 64,
    "use_window_frames": True,       # Achievable on resin
    "use_individual_balusters": True,
    "use_arched_windows": True,
}
```

### 8.2 Overall Piece Dimension Guidelines

| Parameter | Minimum | Typical | Maximum |
|---|---|---|---|
| Total height (incl. base) | 8mm | 12-18mm | 25mm |
| Building footprint width | 6mm | 8-15mm | 20mm |
| Building footprint depth | 6mm | 8-12mm | 18mm |
| Base footprint width | 8mm | 10-16mm | 22mm |
| Base footprint depth | 8mm | 10-14mm | 20mm |
| Base thickness | 0.8mm | 1.0-1.5mm | 2.0mm |
| Floor height (per story) | 1.5mm | 2.0-3.0mm | 4.0mm |
| Number of floors | 1 | 2-4 | 8 (skyscraper) |

### 8.3 Validation Checklist (for `validation/checks.py`)

The validation module should verify every generated mesh against these criteria:

1. **Watertight:** `trimesh.Trimesh.is_watertight == True`
2. **Positive volume:** `trimesh.Trimesh.volume > 0`
3. **Correct orientation:** Bounding box `min_z >= -0.001` (base at Z=0)
4. **Reasonable size:** Bounding box fits within 25mm x 25mm x 30mm
5. **Not too small:** Bounding box exceeds 5mm in all three dimensions
6. **Triangle count:** Between 100 and 200,000 triangles
7. **No degenerate triangles:** All triangle areas > 1e-10 mm^2
8. **Consistent normals:** All face normals point outward (trimesh checks this)
9. **Single connected component:** The mesh is one piece, not floating parts
10. **Minimum wall thickness:** Sample-based check that no wall is thinner than
    the profile minimum (this is expensive; can be optional)

### 8.4 Boolean Operation Workflow

The recommended order of operations for assembling a hotel piece, designed to
minimize boolean artifacts:

```
1. Create main body solid (extruded floor plan x height)
2. Create base slab (slightly larger footprint, overlaps body by 0.1mm)
3. Union: body + base = shell

4. Create ALL window cutout volumes (overshooting 0.1mm on both sides)
5. Create ALL door cutout volumes (overshooting 0.1mm on both sides)
6. Create ALL floor groove cutout volumes (if any)
7. Batch union all cutout volumes into one single cutout solid
8. Difference: shell - cutout_batch = carved_shell

9. Create ALL additive features:
   - Roof geometry (overlapping wall tops by 0.1mm)
   - Window frames (embedded 0.1mm into wall)
   - Balconies (embedded 0.1mm into wall)
   - Columns (embedded 0.1mm into wall/base)
   - Cornices (embedded 0.1mm into wall)
   - Any other decorative features
10. Batch union all additive features into one single addition solid
11. Union: carved_shell + addition_batch = final_model

12. Validate final_model
13. Export as STL/GLB
```

This three-phase approach (shell -> subtract -> add) with batched booleans is
optimal for both performance and robustness. Performing one large boolean operation
is more reliable than many small sequential ones, because each boolean introduces
a small chance of numerical edge cases.

---

## Appendix: Key Numbers at a Glance

For quick reference during development, here are the most frequently needed values:

```
WALL THICKNESS:     0.8mm (FDM)    0.5mm (resin)
FEATURE MINIMUM:    0.6mm (FDM)    0.2mm (resin)
COLUMN DIAMETER:    0.8mm (FDM)    0.4mm (resin)
MAX OVERHANG:       45 deg (FDM)   55 deg (resin)
BOOLEAN OVERSHOOT:  0.1mm          0.1mm
BOOLEAN EMBED:      0.1mm          0.1mm
BASE THICKNESS:     1.2mm (FDM)    1.0mm (resin)
BASE CHAMFER:       0.3mm (FDM)    0.2mm (resin)
CYLINDER SEGMENTS:  diam * 8       diam * 12
TARGET TRIANGLES:   500-20,000     500-20,000
MAX TRIANGLES:      200,000        200,000
```

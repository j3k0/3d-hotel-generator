# Architectural Styles for Procedural Hotel Generation

> Reference guide for generating 3D-printable miniature hotel game pieces (~1-2cm tall) using CSG operations.

---

## 1. Modern

**Silhouette**: Clean rectangular box with flat roof. Horizontal emphasis. At tiny scale, recognizable by its stark geometry and lack of traditional roofline.

### Floor Plan & Massing
- Rectangular footprint, optionally L-shaped or with a cantilevered wing
- Floors stack uniformly — no setbacks required
- Optional penthouse box: smaller rectangle offset on top floor
- Cantilever: one section overhangs the base by 10-20% of width

### Parameters
| Parameter | Range | Notes |
|-----------|-------|-------|
| floors | 3-8 | Typically mid-rise |
| width | 4-8mm | At print scale |
| depth | 3-6mm | Rectangular proportion |
| cantilever_ratio | 0.0-0.2 | Overhang fraction |
| has_penthouse | bool | Smaller top box |

### Windows
- Regular grid pattern, uniform spacing
- Horizontal band windows (wider than tall, ratio ~2:1)
- At miniature scale: shallow horizontal grooves across facade
- Floor-to-ceiling glazing on ground floor (single wide recess)

### Roof
- Flat slab — simply the top face of the extrusion
- Optional: thin parapet wall (0.2mm raised edge)
- Penthouse: small box centered or offset on roof, 60-70% of main footprint

### CSG Construction
```
body = Box(width, depth, height)
if cantilever:
    wing = Box(wing_w, wing_d, wing_h)
    wing = translate(wing, overhang_x, 0, base_z)
    body = union(body, wing)
if penthouse:
    ph = Box(width*0.6, depth*0.6, floor_h)
    ph = translate(ph, offset_x, offset_y, height)
    body = union(body, ph)
windows = grid_of_boxes(rows=floors, cols=4-6, recess=0.3mm)
body = difference(body, windows)
```

### Decorative Features
- Horizontal score lines between floors (0.1mm deep grooves)
- Ground floor recessed entry (wider/taller cutout)
- Balcony slabs: thin protrusions on one facade

### Complexity: Low
Simplest style to generate. Good starting point for implementation.

---

## 2. Skyscraper

**Silhouette**: Very tall and slender tower, often with a wider base podium. Crown element at top. Instantly recognizable by extreme height-to-width ratio.

### Floor Plan & Massing
- Two-part composition: podium (2-3 floors, full lot width) + tower (narrower, many floors)
- Tower footprint is 50-70% of podium footprint
- Optional setbacks every N floors for Art Deco variant
- Crown: decorative top element (spire, flat mechanical penthouse, or angled cap)

### Parameters
| Parameter | Range | Notes |
|-----------|-------|-------|
| total_floors | 8-20 | At scale, max ~20mm |
| podium_floors | 2-3 | Wider base |
| tower_width | 2-4mm | Slender |
| tower_depth | 2-4mm | Often square |
| podium_width | 4-7mm | Full lot |
| crown_type | flat/spire/cap | Top element |

### Windows
- Curtain wall grid: dense regular grid of small square recesses
- At miniature scale: vertical score lines work better than individual windows
- Podium may have larger ground-floor openings

### Roof
- Flat top with mechanical penthouse box
- Or: pointed spire (cone or pyramid, 1-2mm tall)
- Or: angled cap (wedge shape)

### CSG Construction
```
podium = Box(pod_w, pod_d, pod_h)
tower = Box(twr_w, twr_d, twr_h)
tower = translate(tower, center_offset_x, center_offset_y, pod_h)
body = union(podium, tower)

if crown == 'spire':
    spire = Cylinder(r_base=0.5, r_top=0, h=2.0)
    body = union(body, translate(spire, cx, cy, total_h))
elif crown == 'cap':
    cap = Box(twr_w*1.1, twr_d*1.1, 0.5)
    body = union(body, translate(cap, cx, cy, total_h))

# Curtain wall texture: vertical grooves
for i in range(n_grooves):
    groove = Box(0.15, depth+1, twr_h)
    body = difference(body, translate(groove, x_i, 0, pod_h))
```

### Decorative Features
- Vertical pilaster lines along tower facades
- Podium canopy (thin slab protruding at podium roof level)
- Crown ornament distinguishes the top

### Complexity: Medium
The podium+tower composition is the key challenge. Crown variants add variety.

---

## 3. Art Deco

**Silhouette**: Stepped/ziggurat profile — the building gets narrower as it goes up in 2-3 tiers. Vertical emphasis with geometric ornament at the crown.

### Floor Plan & Massing
- Rectangular base, then 2-3 setbacks creating a wedding-cake profile
- Each tier is 70-80% the footprint of the one below
- Tiers are typically 3-5 floors each
- Strong vertical center axis

### Parameters
| Parameter | Range | Notes |
|-----------|-------|-------|
| tiers | 2-4 | Number of setback levels |
| base_width | 5-8mm | Widest tier |
| base_depth | 4-6mm | |
| setback_ratio | 0.7-0.85 | Each tier shrinks by this |
| tier_floors | 2-5 | Floors per tier |
| crown_height | 0.5-1.5mm | Decorative top |

### Windows
- Tall narrow windows (taller than wide, ratio ~1:2.5)
- Grouped in vertical bands of 2-3 windows
- At miniature scale: vertical groove clusters

### Roof
- Flat top on final tier
- Crown ornament: geometric shape — pyramid, stepped pyramid, or pointed finial
- Vertical fins radiating from crown (thin slabs)

### CSG Construction
```
tiers = []
current_w, current_d = base_w, base_d
current_z = 0
for i in range(num_tiers):
    h = tier_floors[i] * floor_h
    tier = Box(current_w, current_d, h)
    tier = translate(tier, -current_w/2, -current_d/2, current_z)
    tiers.append(tier)
    current_z += h
    current_w *= setback_ratio
    current_d *= setback_ratio

body = union_all(tiers)

# Crown: stepped pyramid
crown = Box(current_w*0.8, current_d*0.8, 0.3)
crown2 = Box(current_w*0.5, current_d*0.5, 0.3)
crown = union(translate(crown, ..., current_z),
              translate(crown2, ..., current_z+0.3))
body = union(body, crown)

# Vertical fins on top tier
for angle in [0, 90, 180, 270]:
    fin = Box(0.15, current_d*0.6, crown_h)
    fin = rotate(fin, angle)
    body = union(body, translate(fin, ..., current_z))
```

### Decorative Features
- Vertical fins/pilasters on upper tiers (thin protruding slabs)
- Geometric crown ornament (chevrons, zigzags approximated as stepped blocks)
- Each setback creates a visible ledge/terrace
- At miniature scale, the stepped silhouette IS the decoration

### Complexity: Medium-High
Multiple tiers require careful alignment. Crown ornament adds detail.

---

## 4. Classical

**Silhouette**: Symmetrical rectangular building with prominent triangular pediment on top. Columned entrance facade. Formal and stately.

### Floor Plan & Massing
- Strictly symmetrical rectangular footprint
- 2-4 floors, relatively wide and not too tall
- Central entrance bay may project slightly forward
- Portico: row of columns supporting a pediment

### Parameters
| Parameter | Range | Notes |
|-----------|-------|-------|
| floors | 2-4 | Low-rise |
| width | 5-9mm | Wide facade |
| depth | 3-5mm | |
| num_columns | 4-6 | Even number |
| has_portico | bool | Projecting entrance |
| pediment_height | 0.5-1.0mm | Triangle on top |

### Windows
- Symmetrically placed, evenly spaced
- Slightly taller than wide (ratio ~1:1.5)
- Aligned vertically floor-to-floor
- Ground floor windows/doors may be taller (1.5x)

### Roof
- Low-pitch gabled roof behind the pediment, or flat with parapet
- Triangular pediment across the front facade (key identifier)
- Pediment: triangular prism, very shallow depth

### CSG Construction
```
body = Box(width, depth, height)

# Pediment: triangular prism across front face
pediment = triangular_prism(width, pediment_depth, pediment_h)
pediment = translate(pediment, 0, 0, height)
body = union(body, pediment)

# Columns/pilasters: thin cylinders or boxes along front face
for i in range(num_columns):
    col = Cylinder(r=0.2, h=ground_floor_h)
    x = column_spacing * i + margin
    col = translate(col, x, -0.1, 0)
    body = union(body, col)

# Entablature: thin horizontal band above columns
band = Box(width, 0.3, 0.3)
band = translate(band, 0, -0.1, ground_floor_h)
body = union(body, band)

# Window recesses
windows = symmetric_grid(rows=floors, cols=5, recess=0.3)
body = difference(body, windows)
```

### Decorative Features
- Pilasters (flat column shapes) on facade — rectangular protrusions
- Horizontal entablature band between ground floor and upper floors
- Triangular pediment is the dominant feature at small scale
- Cornice line at roofline (thin protruding ledge)

### Complexity: Medium
Pediment geometry (triangular prism) and column placement require care. Symmetry must be enforced.

---

## 5. Mediterranean

**Silhouette**: Warm, chunky building with a prominent hip or barrel roof. Thick walls, arched openings, possibly an internal courtyard. Recognizable by the broad sloping roof.

### Floor Plan & Massing
- Rectangular or U-shaped (with courtyard)
- 2-4 floors, chunky proportions (walls feel thick)
- Ground floor may have arched loggia (recessed arcade)
- Slightly irregular massing — wings at different heights

### Parameters
| Parameter | Range | Notes |
|-----------|-------|-------|
| floors | 2-4 | Low to mid-rise |
| width | 5-8mm | |
| depth | 4-6mm | |
| plan_type | rect/U/L | Floor plan shape |
| roof_type | hip/barrel | Roof style |
| has_loggia | bool | Ground floor arcade |
| courtyard_ratio | 0.3-0.5 | For U-plan |

### Windows
- Arched tops (at miniature scale: slightly rounded top on rectangular recess)
- Irregular spacing acceptable — some walls left blank
- Smaller windows on upper floors
- Ground floor: larger arched openings if loggia present

### Roof
- **Hip roof**: pyramid-like form, slopes on all four sides. Constructed by intersecting angled planes with the building box.
- **Barrel roof**: half-cylinder along the ridge line
- Roof overhangs walls slightly (0.2-0.3mm)
- Roof sits relatively high — prominent visual feature

### CSG Construction
```
body = Box(width, depth, wall_height)

if plan_type == 'U':
    courtyard = Box(width*cy_ratio, depth*0.6, wall_height+1)
    courtyard = translate(courtyard, cx, -0.1, 0)
    body = difference(body, courtyard)

# Hip roof: intersection of box with angled planes
roof_block = Box(width+0.4, depth+0.4, roof_height)
roof_block = translate(roof_block, -0.2, -0.2, wall_height)
# Cut four angled planes to create hip form
for side in ['front','back','left','right']:
    cutter = angled_halfspace(side, roof_pitch)
    roof_block = intersection(roof_block, cutter)
body = union(body, roof_block)

# OR barrel roof:
barrel = Cylinder(r=width/2, h=depth+0.4)
barrel = rotate(barrel, 90, axis='x')
barrel = translate(barrel, width/2, -0.2, wall_height)
body = union(body, barrel)

# Loggia: row of arched cutouts on ground floor
if has_loggia:
    for i in range(num_arches):
        arch = arch_shape(w=arch_w, h=arch_h)
        body = difference(body, translate(arch, x_i, -0.1, 0))
```

### Decorative Features
- Thick wall impression (no window reveals needed — walls look solid)
- Arched openings on ground floor
- Roof is the dominant decorative element
- Optional: tiny balcony protrusions on upper floors

### Complexity: Medium-High
Roof geometry (especially hip roof via plane intersections) is the main challenge. U-shaped plans add complexity.

---

## 6. Townhouse

**Silhouette**: Narrow, tall rectangle with a distinctive mansard roof (double-slope). Row-house proportions — taller than wide. Recognizable by the steep roof profile.

### Floor Plan & Massing
- Narrow rectangular footprint (width < depth, or width ≈ depth but narrow)
- 3-5 floors, vertically proportioned
- Facade is the narrow side
- Optional: bay window protrusion on facade

### Parameters
| Parameter | Range | Notes |
|-----------|-------|-------|
| floors | 3-5 | Tall and narrow |
| width | 2-4mm | Narrow facade |
| depth | 3-5mm | Deeper than wide |
| roof_type | mansard/gable | Usually mansard |
| has_bay_window | bool | Projecting window box |
| has_stoop | bool | Raised entry steps |
| has_cornice | bool | Decorative top edge |

### Windows
- Regular vertical stacking — windows aligned per floor
- 2-3 windows per floor on narrow facade
- Taller windows on the main floor (floor 2, the "piano nobile")
- Bay window: a small projecting box with 3 window faces

### Roof
- **Mansard**: distinctive double-slope — near-vertical lower portion and shallow upper portion. Creates usable attic space.
- At miniature scale: a box with angled sides (trapezoid cross-section) plus a small flat or shallow-gable top
- Dormers: tiny protruding boxes on the mansard slope (optional at this scale)

### CSG Construction
```
body = Box(width, depth, wall_height)

# Stoop: small box at entrance
if has_stoop:
    stoop = Box(width*0.4, 0.5, floor_h*0.3)
    body = union(body, translate(stoop, cx, -0.5, 0))

# Bay window: projecting box on facade
if has_bay_window:
    bay = Box(width*0.5, 0.4, floor_h*2)
    bay = translate(bay, cx, -0.4, floor_h)
    body = union(body, bay)

# Mansard roof: trapezoid extrusion
# Lower steep portion
mansard_lower = tapered_box(
    bottom=(width, depth),
    top=(width*0.85, depth*0.85),
    height=mansard_lower_h
)
mansard_lower = translate(mansard_lower, 0, 0, wall_height)
# Upper shallow portion
mansard_upper = Box(width*0.85, depth*0.85, mansard_upper_h)
mansard_upper = translate(mansard_upper, ..., wall_height+mansard_lower_h)
body = union(body, mansard_lower, mansard_upper)

# Cornice: thin protruding ledge at roofline
if has_cornice:
    cornice = Box(width+0.3, 0.2, 0.15)
    body = union(body, translate(cornice, -0.15, -0.1, wall_height))

# Windows
windows = grid(rows=floors, cols=2, recess=0.3)
body = difference(body, windows)
```

### Decorative Features
- Mansard roof profile is the key identifier
- Cornice line at roof transition (thin protruding ledge)
- Bay window protrusion on facade
- Stoop (raised entry platform)
- At miniature scale: the tall-narrow proportion + mansard roof is sufficient

### Complexity: Medium
Mansard roof (tapered box) is the trickiest part. Bay windows add a nice touch.

---

## 7. Tropical

**Silhouette**: Low-slung building with deep overhanging roofs, possibly on stilts. Multi-tier roofs create a layered look. Open, airy feeling even at small scale.

### Floor Plan & Massing
- Wide, low proportions (wider than tall)
- May be elevated on stilts (open ground level)
- Multiple wings or pavilions connected together
- L-shape or spread-out plan common

### Parameters
| Parameter | Range | Notes |
|-----------|-------|-------|
| floors | 1-3 | Low-rise |
| width | 5-9mm | Wide spread |
| depth | 4-7mm | |
| on_stilts | bool | Elevated base |
| stilt_height | 0.5-1.0mm | Open ground level |
| roof_tiers | 1-3 | Layered roofs |
| overhang | 0.5-1.0mm | Deep eaves |
| num_wings | 1-2 | Building wings |

### Windows
- Large openings (suggesting open-air design)
- Full-width openings on some facades
- Minimal window frames — just rectangular cutouts
- Louver suggestion: horizontal score lines across openings

### Roof
- **Multi-tier hip roof**: 2-3 overlapping hip roofs at different heights
- Very deep overhangs extending well past walls
- Slight upward curve at eave tips (optional)
- Each wing may have its own roof

### CSG Construction
```
# Stilts: thin cylinders or boxes at corners
if on_stilts:
    for corner in corners:
        stilt = Box(0.3, 0.3, stilt_h)
        body = union(body, translate(stilt, corner.x, corner.y, 0))
    floor_slab = Box(width, depth, 0.2)
    body = union(body, translate(floor_slab, 0, 0, stilt_h))
    base_z = stilt_h
else:
    base_z = 0

# Main volume
main = Box(width, depth, wall_height)
main = translate(main, 0, 0, base_z)
body = union(body, main)

# Multi-tier roof with deep overhangs
for tier in range(roof_tiers):
    tier_w = width * (1.0 - tier * 0.25) + overhang * 2
    tier_d = depth * (1.0 - tier * 0.25) + overhang * 2
    tier_h = roof_tier_height
    roof = hip_roof(tier_w, tier_d, tier_h, pitch=30)
    z = base_z + wall_height + tier * (tier_h * 0.6)
    roof = translate(roof, centered, centered, z)
    body = union(body, roof)

# Large openings
for side in open_sides:
    opening = Box(width*0.7, wall_thickness+0.2, wall_height*0.6)
    body = difference(body, translate(opening, ...))
```

### Decorative Features
- Deep overhanging eaves (the dominant feature at small scale)
- Stilt base creating visible void under the building
- Multi-tier roofline visible in silhouette
- Open/void areas suggesting tropical airiness
- Thin deck/veranda platforms extending beyond walls

### Complexity: Medium-High
Multi-tier roofs and stilt structures require careful positioning. The "open" feel is achieved through generous cutouts.

---

## 8. Victorian

**Silhouette**: Busy, asymmetric outline with corner turret, multiple gables, and bay windows. The most complex and visually distinctive silhouette. Recognizable by its "busy" roofline.

### Floor Plan & Massing
- Asymmetric L-shaped or T-shaped plan
- Corner turret (cylindrical or polygonal tower) at plan intersection
- 2-4 floors with varied heights per wing
- Bay windows projecting from facade

### Parameters
| Parameter | Range | Notes |
|-----------|-------|-------|
| floors | 2-4 | |
| main_width | 4-7mm | Main wing |
| main_depth | 3-5mm | |
| side_width | 2-4mm | Side wing |
| side_depth | 2-4mm | |
| turret_radius | 0.5-1.0mm | Corner tower |
| turret_height | extra 1-2 floors above main |
| num_gables | 1-3 | Roof gables |
| has_bay_window | bool | Facade protrusion |

### Windows
- Varied sizes — larger on lower floors, smaller on upper
- Bay windows: 3-sided projecting boxes
- Turret windows: small rectangular cutouts around cylinder
- Dormer windows in roof gables

### Roof
- **Multi-gable**: primary ridge with cross-gables on wings
- Turret cap: cone (cylinder with r_top=0) or pointed polygon
- Dormers: small gabled boxes protruding from roof slope
- Complex roofline is the key silhouette feature

### CSG Construction
```
# Main wing
main = Box(main_w, main_d, main_h)
# Side wing (L-shape)
side = Box(side_w, side_d, side_h)
side = translate(side, main_w, 0, 0)  # or perpendicular
body = union(main, side)

# Corner turret at intersection
turret = Cylinder(r=turret_r, h=turret_h)
turret = translate(turret, main_w, 0, 0)  # at corner
body = union(body, turret)

# Turret cap: cone
cap = Cylinder(r_bottom=turret_r*1.2, r_top=0, h=1.5)
cap = translate(cap, turret_x, turret_y, turret_h)
body = union(body, cap)

# Main gable roof
main_roof = gable_roof(main_w, main_d, roof_h, ridge_axis='x')
main_roof = translate(main_roof, 0, 0, main_h)
body = union(body, main_roof)

# Cross gable on side wing
side_roof = gable_roof(side_w, side_d, roof_h*0.8, ridge_axis='y')
side_roof = translate(side_roof, main_w, 0, side_h)
body = union(body, side_roof)

# Bay window
if has_bay_window:
    bay = three_sided_bay(w=1.0, protrusion=0.4, h=floor_h*2)
    body = union(body, translate(bay, bx, by, floor_h))

# Dormers (tiny gabled boxes on roof slope)
for dx in dormer_positions:
    dormer = Box(0.5, 0.4, 0.4)
    dormer_roof = tiny_gable(0.5, 0.4, 0.3)
    d = union(dormer, translate(dormer_roof, 0, 0, 0.4))
    body = union(body, translate(d, dx, -0.2, main_h + roof_offset))
```

### Decorative Features
- Corner turret with conical cap — most distinctive feature
- Multiple roof gables creating complex skyline
- Bay window protrusions
- Wrap-around porch (thin platform + posts at ground level)
- At miniature scale: turret + asymmetric roofline is sufficient for recognition

### Complexity: High
Most complex style. Asymmetric plan, turret geometry, multi-gable roof, and bay windows all add up. Recommend implementing last.

---

## Style Comparison Matrix

| Style | Floors | Roof | Plan Shape | Key Feature | Complexity |
|-------|--------|------|-----------|-------------|------------|
| Modern | 3-8 | Flat | Rect/L | Clean box + cantilever | Low |
| Skyscraper | 8-20 | Flat+crown | Rect | Podium+tower, height | Medium |
| Art Deco | 6-15 | Stepped | Rect | Ziggurat setbacks | Medium-High |
| Classical | 2-4 | Pediment | Rect | Columns + pediment | Medium |
| Mediterranean | 2-4 | Hip/barrel | Rect/U | Thick walls + arches | Medium-High |
| Townhouse | 3-5 | Mansard | Narrow rect | Tall narrow + mansard | Medium |
| Tropical | 1-3 | Multi-tier hip | L/spread | Stilts + deep overhangs | Medium-High |
| Victorian | 2-4 | Multi-gable | L/T | Turret + busy roofline | High |

## Implementation Order (Recommended)

1. **Modern** — simplest geometry, establishes base patterns
2. **Skyscraper** — adds podium+tower composition
3. **Townhouse** — introduces mansard roof, bay windows
4. **Classical** — pediment (triangular prism), columns
5. **Art Deco** — iterative setbacks, crown ornament
6. **Mediterranean** — hip/barrel roof, arched openings, U-plans
7. **Tropical** — stilts, multi-tier roofs, open voids
8. **Victorian** — full complexity: asymmetric plan, turret, multi-gable

## Printability Notes

- **Minimum feature size**: ~0.2mm for FDM, ~0.1mm for resin
- **Overhangs**: Keep below 45 degrees or ensure supported
- **Thin walls**: Minimum 0.3mm for structural integrity
- **Windows**: Recessed cutouts (not through-holes) work best at this scale
- **Roofs**: Solid geometry, not thin shells
- **Turrets/cylinders**: Need sufficient polygon count (16+ sides) for smooth appearance
- **Base**: All models need a flat base for bed adhesion and game piece stability

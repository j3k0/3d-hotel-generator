# Procedural Generation Techniques for 3D Hotel Buildings

> Algorithms and patterns for generating 3D-printable miniature hotel buildings (~1-2cm tall) using CSG operations with manifold3d.

---

## 1. Shape Grammars for Architectural Generation

Shape grammars define a set of production rules that recursively transform simple shapes into complex architectural forms. Each rule takes a labeled shape and replaces it with a more detailed composition.

### Grammar Structure

```
Rule: <symbol> → <replacement>

Building → Base + Floors + Roof
Floors  → Floor * N
Floor   → FloorSlab + Walls + Windows
Walls   → WallSegment * 4  (for rectangular plan)
Roof    → GableRoof | HipRoof | FlatRoof | MansardRoof
```

### Production Rules for Hotels

```python
def apply_grammar(symbol, params, rng):
    """Apply shape grammar rules to generate building geometry."""
    if symbol == 'Building':
        base = apply_grammar('Base', params, rng)
        floors = apply_grammar('Floors', params, rng)
        roof = apply_grammar('Roof', params, rng)
        return union(base, floors, roof)

    elif symbol == 'Floors':
        parts = []
        z = params['base_height']
        for i in range(params['num_floors']):
            floor_params = {**params, 'floor_index': i, 'z': z}
            # Apply setback rule if style requires it
            if params.get('setback_per_floor'):
                shrink = params['setback_per_floor'] * i
                floor_params['width'] -= shrink
                floor_params['depth'] -= shrink
            parts.append(apply_grammar('Floor', floor_params, rng))
            z += params['floor_height']
        return union_all(parts)

    elif symbol == 'Floor':
        slab = Box(params['width'], params['depth'], params['floor_height'])
        slab = translate(slab, params.get('x', 0), params.get('y', 0), params['z'])
        windows = apply_grammar('Windows', params, rng)
        return difference(slab, windows)

    elif symbol == 'Windows':
        return generate_window_grid(params)

    elif symbol == 'Roof':
        return ROOF_GENERATORS[params['roof_type']](params)
```

### Key Principles
- **Locality**: Each rule only needs to know about its immediate context
- **Composability**: Rules can be mixed/matched across architectural styles
- **Parameterization**: Rules are driven by numeric parameters, not hardcoded geometry
- **Stochastic variation**: Random choices within rules create variety

---

## 2. Parametric Building Generation

Every building is fully determined by a parameter dictionary. The same generation code produces wildly different buildings depending on parameter values.

### Parameter Categories

```python
@dataclass
class BuildingParams:
    # === Massing ===
    width: float          # 2-9mm at print scale
    depth: float          # 2-7mm
    num_floors: int       # 1-20
    floor_height: float   # 0.6-1.0mm per floor
    plan_shape: str       # 'rect', 'L', 'U', 'T'

    # === Style-specific ===
    style: str            # 'modern', 'victorian', etc.
    roof_type: str        # 'flat', 'gable', 'hip', 'mansard', 'barrel'
    roof_pitch: float     # 15-60 degrees
    has_setbacks: bool
    setback_ratio: float  # 0.7-0.95

    # === Facade ===
    window_width: float   # 0.2-0.5mm
    window_height: float  # 0.3-0.8mm
    window_cols: int      # 2-8 per facade
    window_recess: float  # 0.1-0.4mm depth
    window_style: str     # 'rect', 'arch', 'band'

    # === Features ===
    has_turret: bool
    has_bay_window: bool
    has_balconies: bool
    has_columns: bool
    has_portico: bool
    has_stilts: bool

    # === Randomization ===
    seed: int             # For reproducible generation
```

### Parameter Presets by Style

```python
STYLE_PRESETS = {
    'modern': {
        'num_floors': (3, 8),
        'roof_type': 'flat',
        'window_style': 'band',
        'has_setbacks': False,
        'window_cols': (4, 8),
    },
    'art_deco': {
        'num_floors': (6, 15),
        'roof_type': 'flat',  # with crown
        'has_setbacks': True,
        'setback_ratio': (0.7, 0.85),
    },
    'victorian': {
        'num_floors': (2, 4),
        'plan_shape': 'L',
        'roof_type': 'gable',
        'has_turret': True,
        'has_bay_window': True,
    },
    # ... etc
}

def sample_params(style: str, rng: random.Random) -> BuildingParams:
    """Sample random parameters within style-appropriate ranges."""
    preset = STYLE_PRESETS[style]
    params = {}
    for key, value in preset.items():
        if isinstance(value, tuple) and len(value) == 2:
            if isinstance(value[0], int):
                params[key] = rng.randint(value[0], value[1])
            else:
                params[key] = rng.uniform(value[0], value[1])
        else:
            params[key] = value
    return BuildingParams(**params)
```

### Parameter Validation

```python
def validate_params(params: BuildingParams) -> BuildingParams:
    """Enforce printability constraints on parameters."""
    # Minimum wall thickness
    min_wall = 0.3  # mm
    # Minimum feature size
    min_feature = 0.2  # mm

    # Ensure building isn't too slender
    max_aspect = 6.0  # height:width
    total_h = params.num_floors * params.floor_height
    if total_h / params.width > max_aspect:
        params.num_floors = int(max_aspect * params.width / params.floor_height)

    # Ensure windows fit in walls
    facade_w = params.width - 2 * min_wall
    max_cols = int(facade_w / (params.window_width + min_wall))
    params.window_cols = min(params.window_cols, max_cols)

    # Ensure window recess doesn't pierce wall
    params.window_recess = min(params.window_recess, params.depth * 0.3)

    return params
```

---

## 3. Facade Generation Algorithms

Facades are the most visually important part of a miniature building. The algorithm places windows, doors, and decorative elements on each face of the building.

### Grid-Based Window Placement

```python
def generate_facade_windows(
    facade_width: float,
    facade_height: float,
    num_floors: int,
    cols_per_floor: int,
    window_w: float,
    window_h: float,
    recess_depth: float,
    style: str = 'rect'
) -> list[Manifold]:
    """Generate window cutout geometry for one facade."""
    cutouts = []
    floor_h = facade_height / num_floors

    # Margins
    side_margin = (facade_width - cols_per_floor * window_w) / (cols_per_floor + 1)
    bottom_margin = (floor_h - window_h) * 0.4  # windows sit in lower portion

    for floor in range(num_floors):
        floor_z = floor * floor_h + bottom_margin

        for col in range(cols_per_floor):
            x = side_margin + col * (window_w + side_margin)

            if style == 'rect':
                win = Box(window_w, recess_depth, window_h)
            elif style == 'arch':
                win = arch_window(window_w, window_h, recess_depth)
            elif style == 'band':
                # Horizontal band window — full width of bay
                win = Box(window_w * 1.5, recess_depth, window_h * 0.6)

            cutouts.append(translate(win, x, 0, floor_z))

    return cutouts


def arch_window(w: float, h: float, depth: float) -> Manifold:
    """Create an arched window cutout (rectangle + half-cylinder on top)."""
    rect = Box(w, depth, h - w/2)
    arch = Cylinder(r=w/2, h=depth)
    arch = rotate(arch, 90, axis='x')
    arch = translate(arch, w/2, 0, h - w/2)
    return union(rect, arch)
```

### Door Placement

```python
def add_entrance(body, params):
    """Add entrance door cutout to the front facade."""
    door_w = params.window_width * 1.5
    door_h = params.floor_height * 0.8
    door_depth = params.window_recess * 1.5

    # Center on facade
    door_x = (params.width - door_w) / 2
    door = Box(door_w, door_depth + 0.1, door_h)
    door = translate(door, door_x, -0.1, 0)

    return difference(body, door)
```

### Facade Composition

```python
def apply_facade(body, face, params):
    """Apply window pattern to one face of the building."""
    # Get face dimensions and transform
    if face == 'front':
        fw, fh = params.width, params.total_height
        transform = identity  # front face at y=0
    elif face == 'back':
        fw, fh = params.width, params.total_height
        transform = lambda g: translate(g, 0, params.depth - 0.01, 0)
    elif face == 'left':
        fw, fh = params.depth, params.total_height
        transform = lambda g: rotate(translate(g, ...), 90, 'z')
    elif face == 'right':
        # mirror of left
        ...

    windows = generate_facade_windows(fw, fh, params.num_floors,
                                       params.window_cols, ...)
    for win in windows:
        body = difference(body, transform(win))

    if face == 'front':
        body = add_entrance(body, params)

    return body
```

---

## 4. Roof Generation Techniques

Roofs are critical for architectural identity. Each roof type requires different CSG construction.

### Flat Roof

```python
def flat_roof(width, depth, parapet_h=0.15):
    """Simple flat roof with optional parapet."""
    if parapet_h > 0:
        outer = Box(width, depth, parapet_h)
        inner = Box(width - 0.3, depth - 0.3, parapet_h + 0.1)
        inner = translate(inner, 0.15, 0.15, 0)
        return difference(outer, inner)
    return None  # just the top face of the building
```

### Gable Roof

```python
def gable_roof(width, depth, ridge_height, ridge_axis='x'):
    """Gable roof: triangular cross-section extruded along ridge."""
    # Create as a box and cut two angled planes
    block = Box(width, depth, ridge_height)

    if ridge_axis == 'x':
        # Ridge runs along X axis, slopes on front and back
        # Cut front slope
        front_cutter = half_space(
            point=(0, 0, ridge_height),
            normal=(0, -ridge_height, depth/2)
        )
        # Cut back slope
        back_cutter = half_space(
            point=(0, depth, ridge_height),
            normal=(0, ridge_height, depth/2)
        )
        block = intersection(block, front_cutter)
        block = intersection(block, back_cutter)

    return block


def gable_roof_via_extrusion(width, depth, ridge_height):
    """Alternative: extrude a triangular cross-section."""
    # Define triangle cross-section
    triangle = CrossSection([
        (0, 0),
        (width, 0),
        (width/2, ridge_height)
    ])
    # Extrude along depth
    roof = extrude(triangle, depth)
    return roof
```

### Hip Roof

```python
def hip_roof(width, depth, ridge_height, pitch_deg=35):
    """Hip roof: slopes on all four sides, ridge shorter than building."""
    # Start with a block
    block = Box(width, depth, ridge_height)

    # Ridge length = max(width, depth) - 2 * (ridge_height / tan(pitch))
    inset = ridge_height / math.tan(math.radians(pitch_deg))

    # Cut four angled planes
    # Front slope
    block = cut_slope(block, face='front', inset=inset, height=ridge_height)
    # Back slope
    block = cut_slope(block, face='back', inset=inset, height=ridge_height)
    # Left slope
    block = cut_slope(block, face='left', inset=inset, height=ridge_height)
    # Right slope
    block = cut_slope(block, face='right', inset=inset, height=ridge_height)

    return block
```

### Mansard Roof

```python
def mansard_roof(width, depth, lower_h, upper_h, lower_inset=0.15):
    """Mansard roof: steep lower section + shallow upper section."""
    # Lower section: tapered box (trapezoid cross-section)
    # Use hull of two rectangles at different heights
    bottom_rect = rect_at_z(width, depth, z=0)
    top_rect = rect_at_z(width - lower_inset*2, depth - lower_inset*2, z=lower_h)
    lower = hull(bottom_rect, top_rect)

    # Upper section: low gable or flat on top
    upper_w = width - lower_inset * 2
    upper_d = depth - lower_inset * 2
    upper = gable_roof(upper_w, upper_d, upper_h)
    upper = translate(upper, lower_inset, lower_inset, lower_h)

    return union(lower, upper)
```

### Barrel/Vault Roof

```python
def barrel_roof(width, depth, rise):
    """Barrel vault roof: half-cylinder along the length."""
    radius = (width/2)**2 / (2*rise) + rise/2  # arc radius from chord & rise
    cylinder = Cylinder(r=radius, h=depth)
    cylinder = rotate(cylinder, 90, axis='x')

    # Position: center on building, cut bottom half
    cylinder = translate(cylinder, width/2, 0, -radius + rise)
    cutter = Box(width*2, depth*2, radius)
    cutter = translate(cutter, -width/2, -depth, -radius)
    barrel = difference(cylinder, cutter)

    return barrel
```

### Conical Turret Cap

```python
def turret_cap(radius, height, overhang=0.1):
    """Conical cap for turrets."""
    cone = Cylinder(r_bottom=radius + overhang, r_top=0, h=height)
    return cone
```

---

## 5. Massing Strategies

Massing defines the overall 3D envelope of the building before detail is added.

### Simple Rectangular

```python
def rect_mass(w, d, h):
    return Box(w, d, h)
```

### L-Shape

```python
def l_shape_mass(main_w, main_d, main_h, wing_w, wing_d, wing_h):
    """L-shaped building plan."""
    main = Box(main_w, main_d, main_h)
    wing = Box(wing_w, wing_d, wing_h)
    # Attach wing to one corner
    wing = translate(wing, main_w, 0, 0)
    return union(main, wing)
```

### U-Shape (Courtyard)

```python
def u_shape_mass(width, depth, height, courtyard_w, courtyard_d):
    """U-shaped building with courtyard."""
    outer = Box(width, depth, height)
    courtyard = Box(courtyard_w, courtyard_d, height + 1)
    # Center courtyard on front face
    cx = (width - courtyard_w) / 2
    courtyard = translate(courtyard, cx, -0.1, 0)
    return difference(outer, courtyard)
```

### Podium + Tower

```python
def podium_tower_mass(pod_w, pod_d, pod_h, twr_w, twr_d, twr_h):
    """Podium base with slender tower above."""
    podium = Box(pod_w, pod_d, pod_h)
    tower = Box(twr_w, twr_d, twr_h)
    # Center tower on podium
    tx = (pod_w - twr_w) / 2
    ty = (pod_d - twr_d) / 2
    tower = translate(tower, tx, ty, pod_h)
    return union(podium, tower)
```

### Stepped/Ziggurat

```python
def stepped_mass(base_w, base_d, floor_h, num_tiers, floors_per_tier, shrink_ratio):
    """Stepped massing: each tier is smaller than the one below."""
    parts = []
    w, d = base_w, base_d
    z = 0
    for tier in range(num_tiers):
        h = floors_per_tier * floor_h
        tier_box = Box(w, d, h)
        # Center each tier
        offset_x = (base_w - w) / 2
        offset_y = (base_d - d) / 2
        tier_box = translate(tier_box, offset_x, offset_y, z)
        parts.append(tier_box)
        z += h
        w *= shrink_ratio
        d *= shrink_ratio
    return union_all(parts)
```

### Choosing Massing by Style

```python
STYLE_MASSING = {
    'modern':        ['rect', 'l_shape'],
    'skyscraper':    ['podium_tower'],
    'art_deco':      ['stepped'],
    'classical':     ['rect'],
    'mediterranean': ['rect', 'u_shape'],
    'townhouse':     ['rect'],  # narrow
    'tropical':      ['rect', 'l_shape'],
    'victorian':     ['l_shape'],
}
```

---

## 6. Randomization with Constraints

Variation makes each generated hotel unique, but constraints ensure the result is printable and architecturally coherent.

### Constrained Random Sampling

```python
class ConstrainedSampler:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def uniform(self, low: float, high: float) -> float:
        return self.rng.uniform(low, high)

    def choice(self, options: list, weights: list = None):
        if weights:
            return random.choices(options, weights=weights, k=1)[0]
        return self.rng.choice(options)

    def int_range(self, low: int, high: int) -> int:
        return self.rng.randint(low, high)

    def sample_constrained(self, param_name: str, style: str) -> float:
        """Sample a parameter with style-specific constraints."""
        constraints = PARAM_CONSTRAINTS[style][param_name]
        value = self.uniform(constraints['min'], constraints['max'])

        # Apply dependent constraints
        if 'max_ratio' in constraints:
            dep_param = constraints['ratio_of']
            dep_value = self.current_params[dep_param]
            value = min(value, dep_value * constraints['max_ratio'])

        return value
```

### Printability Constraints

```python
PRINTABILITY_RULES = {
    'min_wall_thickness': 0.3,    # mm
    'min_feature_size': 0.2,      # mm
    'max_overhang_angle': 45,     # degrees from vertical
    'max_aspect_ratio': 6.0,      # height / min(width, depth)
    'min_base_area': 4.0,         # mm² for stability
    'max_unsupported_span': 2.0,  # mm
}

def enforce_printability(params):
    """Post-process params to guarantee printable output."""
    total_h = params.num_floors * params.floor_height
    min_dim = min(params.width, params.depth)

    # Aspect ratio check
    if total_h / min_dim > PRINTABILITY_RULES['max_aspect_ratio']:
        params.num_floors = int(
            PRINTABILITY_RULES['max_aspect_ratio'] * min_dim / params.floor_height
        )

    # Base area check
    if params.width * params.depth < PRINTABILITY_RULES['min_base_area']:
        scale = math.sqrt(PRINTABILITY_RULES['min_base_area'] /
                         (params.width * params.depth))
        params.width *= scale
        params.depth *= scale

    # Window size check
    if params.window_width < PRINTABILITY_RULES['min_feature_size']:
        params.window_width = PRINTABILITY_RULES['min_feature_size']

    return params
```

### Variation Strategies

```python
def add_variation(base_params, rng, variation_level=0.1):
    """Add random variation to base parameters."""
    varied = copy.deepcopy(base_params)
    for key, value in vars(varied).items():
        if isinstance(value, float):
            # Add ±variation_level% random perturbation
            delta = value * variation_level
            new_val = value + rng.uniform(-delta, delta)
            setattr(varied, key, new_val)
        elif isinstance(value, int) and key == 'num_floors':
            # ±1 floor variation
            new_val = value + rng.choice([-1, 0, 0, 1])
            setattr(varied, key, max(1, new_val))
    return enforce_printability(varied)
```

---

## 7. CSG Tree Optimization

Order and structure of CSG operations significantly impacts both performance and correctness.

### Union Batching

```python
# BAD: O(n²) — each union merges with growing result
result = parts[0]
for part in parts[1:]:
    result = union(result, part)

# GOOD: O(n log n) — balanced binary tree of unions
def balanced_union(parts: list[Manifold]) -> Manifold:
    """Union a list of manifolds in a balanced binary tree."""
    if len(parts) == 0:
        return Manifold()
    if len(parts) == 1:
        return parts[0]

    mid = len(parts) // 2
    left = balanced_union(parts[:mid])
    right = balanced_union(parts[mid:])
    return union(left, right)
```

### Batch Operations with manifold3d

```python
# manifold3d supports batch boolean operations natively
from manifold3d import Manifold

# Batch union — much faster than sequential
result = Manifold.batch_boolean(parts, operation='union')

# Or use the compose method
result = Manifold.compose(parts)  # implicit union
```

### Minimizing Boolean Operations

```python
# BAD: subtract each window individually
body = building_box
for window in all_windows:  # might be 50+ windows
    body = difference(body, window)

# GOOD: union all windows first, then subtract once
all_window_cutouts = balanced_union(all_windows)
body = difference(building_box, all_window_cutouts)
```

### Operation Ordering

```python
def build_hotel(params):
    """Optimized CSG construction order."""
    # 1. Build massing (unions of large simple shapes)
    mass = build_massing(params)

    # 2. Collect ALL cutouts (windows, doors, courtyards)
    cutouts = []
    cutouts.extend(generate_all_windows(params))
    cutouts.extend(generate_doors(params))
    if params.plan_shape == 'U':
        cutouts.append(courtyard_void(params))

    # 3. Single batch subtraction
    all_cuts = balanced_union(cutouts)
    body = difference(mass, all_cuts)

    # 4. Add decorative features (unions)
    features = []
    features.extend(generate_cornices(params))
    features.extend(generate_columns(params))
    if params.has_turret:
        features.append(generate_turret(params))

    all_features = balanced_union(features)
    body = union(body, all_features)

    # 5. Add roof (final union)
    roof = generate_roof(params)
    body = union(body, roof)

    return body
```

---

## 8. Component Composition Patterns

Reusable components reduce code duplication and make it easy to mix architectural elements across styles.

### Component Interface

```python
from abc import ABC, abstractmethod

class BuildingComponent(ABC):
    """Base class for composable building components."""

    @abstractmethod
    def generate(self, params: dict) -> Manifold:
        """Generate the component geometry."""
        pass

    @abstractmethod
    def get_bounds(self, params: dict) -> tuple:
        """Return (width, depth, height) bounding box."""
        pass
```

### Reusable Components

```python
class WindowGrid(BuildingComponent):
    """Generates a grid of window cutouts for one facade."""

    def generate(self, params):
        windows = []
        for row in range(params['rows']):
            for col in range(params['cols']):
                w = self.make_window(params)
                x = params['margin'] + col * params['spacing_x']
                z = params['base_z'] + row * params['spacing_z']
                windows.append(translate(w, x, 0, z))
        return balanced_union(windows)

    def make_window(self, params):
        if params.get('arch'):
            return arch_window(params['win_w'], params['win_h'], params['depth'])
        return Box(params['win_w'], params['depth'], params['win_h'])


class RoofComponent(BuildingComponent):
    """Generates roof geometry based on type."""
    TYPES = {
        'flat': flat_roof,
        'gable': gable_roof,
        'hip': hip_roof,
        'mansard': mansard_roof,
        'barrel': barrel_roof,
    }

    def generate(self, params):
        roof_fn = self.TYPES[params['roof_type']]
        return roof_fn(**params['roof_params'])


class Turret(BuildingComponent):
    """Corner turret with conical cap."""

    def generate(self, params):
        r = params['radius']
        h = params['height']
        body = Cylinder(r=r, h=h)
        cap = Cylinder(r_bottom=r * 1.2, r_top=0, h=r * 2)
        cap = translate(cap, 0, 0, h)
        return union(body, cap)


class Balcony(BuildingComponent):
    """Protruding balcony slab with optional railing."""

    def generate(self, params):
        slab = Box(params['width'], params['depth'], 0.15)
        if params.get('railing'):
            rail = Box(params['width'], 0.1, params['rail_h'])
            rail = translate(rail, 0, params['depth'] - 0.1, 0.15)
            return union(slab, rail)
        return slab
```

### Composition Pipeline

```python
class HotelBuilder:
    """Composes building from components."""

    def __init__(self, style: str, params: BuildingParams):
        self.style = style
        self.params = params
        self.components = []

    def add(self, component: BuildingComponent, transform=None):
        self.components.append((component, transform))
        return self

    def build(self) -> Manifold:
        parts = []
        for component, transform in self.components:
            geom = component.generate(self.params)
            if transform:
                geom = transform(geom)
            parts.append(geom)
        return balanced_union(parts)


# Usage
builder = HotelBuilder('victorian', params)
builder.add(MassingComponent())        # Main body
builder.add(WindowGrid(), front_face)  # Front windows
builder.add(WindowGrid(), side_face)   # Side windows
builder.add(Turret(), corner_transform) # Corner turret
builder.add(RoofComponent())           # Roof
builder.add(Entrance())                # Door

hotel = builder.build()
```

---

## 9. Level-of-Detail for Miniature Scale

At 1-2cm tall, many architectural details are too small to print or see. LOD decisions are critical.

### Scale Reality Check

At 1:1000 scale (a 10-story hotel = 1.5cm miniature):
- 1 floor ≈ 0.3-0.5mm
- 1 window ≈ 0.2-0.4mm wide
- 1 column ≈ 0.2mm diameter
- Wall details < 0.1mm → **unprintable**

### What Works at Miniature Scale

| Feature | Minimum Size | Technique |
|---------|-------------|-----------|
| Window | 0.2mm wide | Recessed rectangle (not through-hole) |
| Floor line | 0.1mm deep | Score line / shallow groove |
| Column | 0.2mm dia | Tiny cylinder or square post |
| Balcony | 0.3mm deep | Protruding slab (no railing detail) |
| Cornice | 0.15mm | Protruding ledge |
| Turret | 0.5mm dia | Small cylinder |
| Roof ridge | 0.3mm+ | Formed by angled planes |

### What Doesn't Work

- Window mullions (too thin)
- Door handles, hinges
- Brick/stone texture
- Ornate column capitals
- Railings with balusters
- Roof tiles individually

### LOD Strategy

```python
def should_include_feature(feature: str, scale: float) -> bool:
    """Decide whether a feature is worth generating at this scale."""
    MIN_SIZES = {
        'window_recess': 0.15,
        'balcony': 0.3,
        'column': 0.2,
        'cornice': 0.1,
        'turret': 0.5,
        'dormer': 0.4,
        'floor_line': 0.08,
        'mullion': 0.05,  # too small — skip
        'railing_detail': 0.05,  # too small — skip
    }
    min_size = MIN_SIZES.get(feature, 0.1)
    actual_size = min_size * scale
    return actual_size >= 0.1  # minimum printable feature


def simplify_for_scale(params, scale):
    """Reduce detail level for small-scale printing."""
    if scale < 0.01:  # very small
        params.window_style = 'band'  # horizontal grooves instead of individual windows
        params.has_balconies = False
        params.has_columns = False
        # Increase minimum sizes
        params.window_recess = max(params.window_recess, 0.2)
```

### Silhouette Priority

At miniature scale, the **silhouette** is more important than surface detail:

1. **Roof shape** — most important identifier (visible from above in a board game)
2. **Overall proportions** — tall/short, wide/narrow
3. **Plan shape** — L, U, tower, etc.
4. **Major protrusions** — turrets, bay windows, porticos
5. **Window pattern** — visible as texture, not individual detail
6. **Surface detail** — least important, often omitted

---

## 10. Existing Procedural Building Systems & Lessons Learned

### Notable Systems

**CityEngine (Esri)**
- Commercial procedural city generator
- Uses CGA shape grammar rules
- Split operations divide facades into bays, floors, windows
- Lesson: **split grammars** (subdividing rectangles) are very effective for facades

**Procedural Building Generation (Müller et al., 2006)**
- Seminal paper on shape grammars for architecture
- Rules: split, repeat, component insert
- Lesson: **repeat** operation (placing N copies along an axis) handles most facade patterns

**Wave Function Collapse**
- Constraint propagation for tile-based generation
- Used for 2D layouts, could work for floor plans
- Lesson: **local constraints** between adjacent elements ensure coherence

**Building generation in games (Cities: Skylines, SimCity)**
- Modular component approach: base + middle sections + roof
- Randomized selection from pre-authored component libraries
- Lesson: **modular stacking** (base + N×middle + top) is simple and effective

### Key Lessons for Our System

1. **Start with the silhouette**: Get massing right before adding detail
2. **Use split/repeat as primary operations**: Most architecture is repetitive
3. **Component libraries over pure procedural**: Mix hand-designed elements with procedural placement
4. **Validate early**: Check printability constraints before generating detail
5. **Separate structure from decoration**: Generate the solid body first, then apply surface features
6. **Test at actual print scale**: Features that look good on screen may vanish when printed
7. **Seed-based determinism**: Always use seeded RNG so results are reproducible
8. **Profile and optimize**: CSG operations on complex geometry can be slow — batch operations matter

### Architecture of Our Generator

```
Input: style + seed (+ optional param overrides)
  │
  ├─→ Sample parameters (constrained random)
  │
  ├─→ Validate parameters (printability)
  │
  ├─→ Generate massing (plan shape + floor stacking)
  │
  ├─→ Generate facades (window grids + doors)
  │     └─→ Batch subtract from massing
  │
  ├─→ Generate roof (style-appropriate)
  │     └─→ Union with body
  │
  ├─→ Generate features (turrets, columns, balconies)
  │     └─→ Union with body
  │
  ├─→ Add base plate (flat bottom for printing)
  │
  └─→ Export STL (manifold3d → mesh → STL)
```

---

## Appendix: manifold3d Quick Reference

```python
import manifold3d as m3d
from manifold3d import Manifold, CrossSection

# Primitives
box = Manifold.cube([width, depth, height])
cyl = Manifold.cylinder(height, radius_low, radius_high, circular_segments=32)
sphere = Manifold.sphere(radius, circular_segments=32)

# Transforms
moved = box.translate([x, y, z])
rotated = box.rotate([rx, ry, rz])  # degrees
scaled = box.scale([sx, sy, sz])

# Boolean operations
combined = box + cylinder          # union
cut = box - cylinder               # difference
overlap = box ^ cylinder           # intersection (use & or ^)

# Batch operations
combined = Manifold.batch_boolean(parts, Manifold.OpType.Add)

# Extrusion
cross = CrossSection([[0,0], [1,0], [0.5, 1]])  # triangle
solid = Manifold.extrude(cross, height)

# Hull
hull = Manifold.hull([point_cloud])

# Export
mesh = combined.to_mesh()
# Then use numpy-stl or trimesh to write STL
```

# Web UI Architecture: three.js Preview for 3D-Printable Hotel Models

## Overview

This document details the frontend architecture for the 3D Hotel Generator web UI. The interface is a single-page application (`web/index.html`, `web/app.js`, `web/style.css`) that communicates with a FastAPI backend. Users select an architectural style, adjust parameters via dynamically generated controls, preview the resulting GLB model in real time, and download the final STL for 3D printing.

The design prioritizes fast feedback loops (sub-second preview updates), clear visualization of fine architectural detail at miniature scale (1-2 cm tall game pieces), and a responsive layout that works on both desktop and tablet screens.

---

## 1. three.js Setup for GLB/GLTF Preview

### Core Scene Initialization

The preview requires a minimal but carefully configured three.js scene. Since models are tiny architectural pieces (roughly 10-20mm bounding box), the camera and scene scale must be tuned accordingly.

```javascript
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

class HotelPreview {
  constructor(containerElement) {
    this.container = containerElement;
    this.currentModel = null;
    this.loadingManager = new THREE.LoadingManager();
    this.gltfLoader = new GLTFLoader(this.loadingManager);

    this.initScene();
    this.initCamera();
    this.initRenderer();
    this.initLighting();
    this.initControls();
    this.initHelpers();
    this.animate();
  }

  initScene() {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xd0d8e0);

    // Ground plane for visual grounding and shadow reception
    const groundGeo = new THREE.PlaneGeometry(80, 80);
    const groundMat = new THREE.ShadowMaterial({ opacity: 0.25 });
    this.ground = new THREE.Mesh(groundGeo, groundMat);
    this.ground.rotation.x = -Math.PI / 2;
    this.ground.position.y = 0;
    this.ground.receiveShadow = true;
    this.scene.add(this.ground);

    // Subtle grid showing scale reference
    const grid = new THREE.GridHelper(60, 60, 0x888888, 0xcccccc);
    grid.position.y = 0.001; // Slightly above ground to avoid z-fighting
    this.scene.add(grid);
  }

  initCamera() {
    const aspect = this.container.clientWidth / this.container.clientHeight;
    this.camera = new THREE.PerspectiveCamera(35, aspect, 0.1, 500);
    // Position for a good default view of a ~20mm tall model
    this.camera.position.set(30, 25, 30);
    this.camera.lookAt(0, 8, 0);
  }

  initRenderer() {
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    });
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.2;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.container.appendChild(this.renderer.domElement);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}
```

### GLTFLoader Configuration

The `GLTFLoader` deserializes `.glb` files returned by the `/generate` endpoint. Since the backend generates models as in-memory binary GLB via trimesh, we load from blobs rather than URLs.

```javascript
loadGLB(arrayBuffer) {
  return new Promise((resolve, reject) => {
    this.gltfLoader.parse(
      arrayBuffer,
      '', // path (empty for in-memory)
      (gltf) => {
        const model = gltf.scene;
        // Apply consistent material to all meshes in the model
        model.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
            child.material = this.createArchitecturalMaterial();
          }
        });
        resolve(model);
      },
      (error) => reject(error)
    );
  });
}
```

**Key point:** The backend's trimesh GLB export may not include materials. The frontend applies its own material to every mesh, giving full control over the architectural appearance. Use `GLTFLoader.parse()` with an `ArrayBuffer` rather than `GLTFLoader.load()` with a URL, because the response comes from a `POST` request (not a simple URL fetch).

### Handling Import Maps vs. Bundlers

For the "no build step" approach specified in the plan (`web/app.js` as a plain script), use an import map in `index.html`:

```html
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
  }
}
</script>
<script type="module" src="app.js"></script>
```

This avoids a bundler while still providing clean ES module imports. Pin the three.js version to prevent breakage from upstream updates.

---

## 2. OrbitControls Configuration

Miniature architectural models need specific orbit behavior: the user should be able to rotate around the model freely, zoom in to examine fine facade detail, and pan slightly to re-center, but never lose the model off-screen.

```javascript
initControls() {
  this.controls = new OrbitControls(this.camera, this.renderer.domElement);

  // Target the vertical center of a typical model (~8mm above ground)
  this.controls.target.set(0, 8, 0);

  // Enable damping for smooth rotation feel
  this.controls.enableDamping = true;
  this.controls.dampingFactor = 0.08;

  // Zoom limits: prevent clipping into the model or losing it at distance
  this.controls.minDistance = 10;   // Closest approach (fills viewport)
  this.controls.maxDistance = 120;  // Furthest zoom out

  // Vertical rotation limits: prevent going below the ground plane
  // or flipping to a disorienting upside-down view
  this.controls.minPolarAngle = 0.1;           // Near top-down
  this.controls.maxPolarAngle = Math.PI * 0.48; // Just above horizon

  // Pan limits: allow slight repositioning but keep model on-screen
  this.controls.enablePan = true;
  this.controls.panSpeed = 0.5;
  // Constrain panning to a reasonable box around origin
  this.controls.addEventListener('change', () => {
    const t = this.controls.target;
    t.x = THREE.MathUtils.clamp(t.x, -20, 20);
    t.y = THREE.MathUtils.clamp(t.y, 0, 30);
    t.z = THREE.MathUtils.clamp(t.z, -20, 20);
  });

  // Scroll speed for zoom
  this.controls.zoomSpeed = 0.8;

  // Touch support for tablet use
  this.controls.touches = {
    ONE: THREE.TOUCH.ROTATE,
    TWO: THREE.TOUCH.DOLLY_PAN,
  };
}
```

### Auto-Framing on Model Load

When a new model loads, the camera should automatically frame it. Compute the bounding box and adjust the controls target and camera distance:

```javascript
frameModel(model) {
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);

  // Reposition orbit target to model center
  this.controls.target.copy(center);

  // Set camera distance to fit model in view (accounting for FOV)
  const fov = this.camera.fov * (Math.PI / 180);
  const distance = (maxDim / 2) / Math.tan(fov / 2) * 1.5;
  const direction = this.camera.position.clone()
    .sub(this.controls.target).normalize();
  this.camera.position.copy(
    this.controls.target.clone().add(direction.multiplyScalar(distance))
  );

  // Update near/far planes to match model scale
  this.camera.near = distance * 0.01;
  this.camera.far = distance * 10;
  this.camera.updateProjectionMatrix();

  this.controls.update();
}
```

### Reset View Button

Provide a "Reset View" button that returns the camera to the default orbital position. Store the initial camera state and restore it:

```javascript
resetView() {
  if (!this.currentModel) return;
  const box = new THREE.Box3().setFromObject(this.currentModel);
  const center = box.getCenter(new THREE.Vector3());
  this.controls.target.copy(center);
  this.camera.position.set(
    center.x + 30, center.y + 25, center.z + 30
  );
  this.controls.update();
}
```

---

## 3. Dynamic Parameter UI Generation

The backend exposes `GET /styles` which returns available styles and their parameter schemas. Each style has different parameters (a Modern hotel has different knobs than a Victorian one). The UI must build controls dynamically from this schema.

### Expected Schema Format

The FastAPI backend uses Pydantic models, which auto-generate JSON Schema. The `/styles` endpoint returns something like:

```json
{
  "styles": [
    {
      "name": "modern",
      "display_name": "Modern",
      "description": "Flat roof, grid windows, clean lines",
      "params_schema": {
        "type": "object",
        "properties": {
          "width": {
            "type": "number",
            "title": "Width",
            "description": "Building width in mm",
            "default": 12,
            "minimum": 6,
            "maximum": 25
          },
          "depth": {
            "type": "number",
            "title": "Depth",
            "default": 10,
            "minimum": 6,
            "maximum": 20
          },
          "num_floors": {
            "type": "integer",
            "title": "Number of Floors",
            "default": 4,
            "minimum": 1,
            "maximum": 8
          },
          "has_penthouse": {
            "type": "boolean",
            "title": "Penthouse",
            "default": false
          },
          "window_style": {
            "type": "string",
            "title": "Window Style",
            "enum": ["grid", "ribbon", "floor_to_ceiling"],
            "default": "grid"
          },
          "printer_type": {
            "type": "string",
            "title": "Printer Type",
            "enum": ["fdm", "resin"],
            "default": "fdm"
          }
        },
        "required": ["width", "depth", "num_floors"]
      }
    }
  ]
}
```

### Schema-Driven Control Builder

Map JSON Schema types to HTML controls:

```javascript
class ParameterUI {
  constructor(containerEl, onChange) {
    this.container = containerEl;
    this.onChange = onChange; // Callback when any param changes
    this.currentParams = {};
    this.controlElements = {};
  }

  buildFromSchema(schema) {
    this.container.innerHTML = '';
    this.currentParams = {};
    this.controlElements = {};

    const properties = schema.properties || {};
    const order = schema['x-param-order'] || Object.keys(properties);

    for (const key of order) {
      const prop = properties[key];
      if (!prop) continue;

      const group = this.createControlGroup(key, prop);
      this.container.appendChild(group);
      this.currentParams[key] = prop.default;
    }
  }

  createControlGroup(key, prop) {
    const group = document.createElement('div');
    group.className = 'param-group';

    const label = document.createElement('label');
    label.textContent = prop.title || key;
    label.htmlFor = `param-${key}`;
    group.appendChild(label);

    if (prop.description) {
      const hint = document.createElement('span');
      hint.className = 'param-hint';
      hint.textContent = prop.description;
      group.appendChild(hint);
    }

    let control;

    if (prop.enum) {
      // Dropdown for enumerated values
      control = this.createSelect(key, prop);
    } else if (prop.type === 'boolean') {
      // Checkbox for booleans
      control = this.createCheckbox(key, prop);
    } else if (prop.type === 'integer' || prop.type === 'number') {
      // Range slider with numeric display for numbers
      control = this.createSlider(key, prop);
    } else if (prop.type === 'string') {
      // Text input fallback
      control = this.createTextInput(key, prop);
    }

    if (control) {
      group.appendChild(control);
      this.controlElements[key] = control;
    }

    return group;
  }

  createSlider(key, prop) {
    const wrapper = document.createElement('div');
    wrapper.className = 'slider-wrapper';

    const input = document.createElement('input');
    input.type = 'range';
    input.id = `param-${key}`;
    input.min = prop.minimum ?? 0;
    input.max = prop.maximum ?? 100;
    input.step = prop.type === 'integer' ? 1 : 0.5;
    input.value = prop.default ?? prop.minimum ?? 0;

    const valueDisplay = document.createElement('span');
    valueDisplay.className = 'slider-value';
    valueDisplay.textContent = input.value;

    input.addEventListener('input', () => {
      const val = prop.type === 'integer'
        ? parseInt(input.value, 10)
        : parseFloat(input.value);
      valueDisplay.textContent = val;
      this.currentParams[key] = val;
      this.onChange(this.currentParams);
    });

    wrapper.appendChild(input);
    wrapper.appendChild(valueDisplay);
    return wrapper;
  }

  createSelect(key, prop) {
    const select = document.createElement('select');
    select.id = `param-${key}`;
    for (const option of prop.enum) {
      const opt = document.createElement('option');
      opt.value = option;
      opt.textContent = option.replace(/_/g, ' ');
      if (option === prop.default) opt.selected = true;
      select.appendChild(opt);
    }
    select.addEventListener('change', () => {
      this.currentParams[key] = select.value;
      this.onChange(this.currentParams);
    });
    return select;
  }

  createCheckbox(key, prop) {
    const wrapper = document.createElement('div');
    wrapper.className = 'checkbox-wrapper';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.id = `param-${key}`;
    input.checked = prop.default ?? false;
    input.addEventListener('change', () => {
      this.currentParams[key] = input.checked;
      this.onChange(this.currentParams);
    });
    wrapper.appendChild(input);
    return wrapper;
  }

  createTextInput(key, prop) {
    const input = document.createElement('input');
    input.type = 'text';
    input.id = `param-${key}`;
    input.value = prop.default ?? '';
    input.addEventListener('input', () => {
      this.currentParams[key] = input.value;
      this.onChange(this.currentParams);
    });
    return input;
  }

  getParams() {
    return { ...this.currentParams };
  }
}
```

### Style Selector Integration

When the user switches styles, fetch the new schema and rebuild controls:

```javascript
async function initStyleSelector(selectEl, paramUI, preview) {
  const response = await fetch('/styles');
  const data = await response.json();
  const styles = data.styles;

  // Populate style dropdown
  for (const style of styles) {
    const opt = document.createElement('option');
    opt.value = style.name;
    opt.textContent = style.display_name;
    selectEl.appendChild(opt);
  }

  // Build a lookup map
  const styleMap = Object.fromEntries(styles.map(s => [s.name, s]));

  selectEl.addEventListener('change', () => {
    const style = styleMap[selectEl.value];
    if (style) {
      paramUI.buildFromSchema(style.params_schema);
      // Trigger initial generation with defaults
      requestPreview(selectEl.value, paramUI.getParams(), preview);
    }
  });

  // Initialize with first style
  if (styles.length > 0) {
    selectEl.value = styles[0].name;
    selectEl.dispatchEvent(new Event('change'));
  }
}
```

---

## 4. Efficient Preview Workflow

The critical interaction loop is: user adjusts slider -> debounced API call -> backend generates GLB -> frontend loads and displays. This must feel responsive while avoiding unnecessary backend work.

### Debounced Parameter Changes

Use a debounce that fires after the user stops adjusting for 300ms. This prevents hammering the API during continuous slider dragging while keeping feedback snappy:

```javascript
function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// Usage: wrap the preview request
const debouncedPreview = debounce((style, params, preview) => {
  requestPreview(style, params, preview);
}, 300);

// Wire into ParameterUI onChange:
paramUI = new ParameterUI(sidebarEl, (params) => {
  debouncedPreview(currentStyle, params, preview);
});
```

### API Call with AbortController

Cancel in-flight requests when a newer request supersedes them. This prevents race conditions where an older response arrives after a newer one:

```javascript
let activeController = null;
let requestGeneration = 0;

async function requestPreview(style, params, preview) {
  // Cancel any in-flight request
  if (activeController) {
    activeController.abort();
  }
  activeController = new AbortController();
  const thisGeneration = ++requestGeneration;

  preview.showLoading(true);

  try {
    const response = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style, ...params }),
      signal: activeController.signal,
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || `Server error ${response.status}`);
    }

    // Guard against stale responses
    if (thisGeneration !== requestGeneration) return;

    const arrayBuffer = await response.arrayBuffer();
    await preview.replaceModel(arrayBuffer);
  } catch (err) {
    if (err.name === 'AbortError') return; // Expected, ignore
    preview.showError(err.message);
  } finally {
    if (thisGeneration === requestGeneration) {
      preview.showLoading(false);
    }
  }
}
```

### Model Replacement with Cleanup

When loading a new GLB, the old model must be properly disposed to avoid GPU memory leaks:

```javascript
async replaceModel(arrayBuffer) {
  // Dispose old model
  if (this.currentModel) {
    this.disposeObject(this.currentModel);
    this.scene.remove(this.currentModel);
    this.currentModel = null;
  }

  // Load new model
  const model = await this.loadGLB(arrayBuffer);
  this.currentModel = model;
  this.scene.add(model);

  // Auto-frame the new model
  this.frameModel(model);
}

disposeObject(obj) {
  obj.traverse((child) => {
    if (child.isMesh) {
      child.geometry.dispose();
      if (Array.isArray(child.material)) {
        child.material.forEach(m => m.dispose());
      } else if (child.material) {
        child.material.dispose();
      }
    }
  });
}
```

### Loading State Feedback

Show a spinner overlay during generation and load. Keep the previous model visible (slightly dimmed) so the viewport is never blank:

```javascript
showLoading(active) {
  const overlay = document.getElementById('loading-overlay');
  overlay.classList.toggle('visible', active);

  // Dim (but do not hide) the current model during loading
  if (this.currentModel) {
    this.currentModel.traverse((child) => {
      if (child.isMesh) {
        child.material.opacity = active ? 0.4 : 1.0;
        child.material.transparent = active;
      }
    });
  }
}
```

---

## 5. Responsive Layout

The layout uses CSS Grid with two primary regions: a 3D viewport occupying the majority of the screen, and a sidebar containing the controls panel.

### HTML Structure

```html
<body>
  <div id="app">
    <header id="top-bar">
      <h1>3D Hotel Generator</h1>
      <div id="global-actions">
        <button id="btn-download-stl" title="Download STL">
          Download STL
        </button>
        <button id="btn-reset-view" title="Reset camera">
          Reset View
        </button>
      </div>
    </header>

    <main id="workspace">
      <div id="viewport-container">
        <!-- three.js canvas renders here -->
        <div id="loading-overlay">
          <div class="spinner"></div>
          <span>Generating model...</span>
        </div>
        <div id="error-toast" class="hidden"></div>
      </div>

      <aside id="sidebar">
        <div id="style-selector-group">
          <label for="style-select">Style</label>
          <select id="style-select"></select>
        </div>
        <div id="params-container">
          <!-- Dynamically generated parameter controls -->
        </div>
      </aside>
    </main>
  </div>
</body>
```

### CSS Layout

```css
/* === Reset & base === */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
               Oxygen, Ubuntu, sans-serif;
  background: #1a1d23;
  color: #e0e0e0;
  overflow: hidden;
  height: 100vh;
}

/* === App shell === */
#app {
  display: grid;
  grid-template-rows: 48px 1fr;
  height: 100vh;
}

#top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: #22262e;
  border-bottom: 1px solid #333;
}

#top-bar h1 {
  font-size: 16px;
  font-weight: 600;
}

/* === Workspace: viewport + sidebar === */
#workspace {
  display: grid;
  grid-template-columns: 1fr 320px;
  overflow: hidden;
}

/* === 3D Viewport === */
#viewport-container {
  position: relative;
  overflow: hidden;
  background: #2a2d35;
}

#viewport-container canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

/* === Sidebar === */
#sidebar {
  background: #22262e;
  border-left: 1px solid #333;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* === Loading overlay === */
#loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
}

#loading-overlay.visible {
  opacity: 1;
  pointer-events: auto;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255,255,255,0.2);
  border-top-color: #4fc3f7;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* === Parameter controls === */
.param-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.param-group label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #aaa;
}

.param-hint {
  font-size: 11px;
  color: #777;
}

.slider-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.slider-wrapper input[type="range"] {
  flex: 1;
  accent-color: #4fc3f7;
}

.slider-value {
  min-width: 32px;
  text-align: right;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: #4fc3f7;
}

select, input[type="text"] {
  width: 100%;
  padding: 6px 8px;
  background: #2a2d35;
  border: 1px solid #444;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
}

/* === Responsive: collapse sidebar on narrow screens === */
@media (max-width: 768px) {
  #workspace {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr auto;
  }

  #sidebar {
    border-left: none;
    border-top: 1px solid #333;
    max-height: 40vh;
    overflow-y: auto;
  }
}
```

### Viewport Resize Handling

The three.js renderer must respond to container size changes (window resize, sidebar toggle):

```javascript
initResizeObserver() {
  this.resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const { width, height } = entry.contentRect;
      if (width === 0 || height === 0) continue;
      this.camera.aspect = width / height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(width, height);
    }
  });
  this.resizeObserver.observe(this.container);
}
```

Using `ResizeObserver` instead of the `window` resize event is critical because the viewport container can change size independently of the window (e.g., when the sidebar collapses on mobile).

---

## 6. Material and Lighting for Architectural Detail

Miniature architectural models need careful lighting to reveal facade detail -- window recesses, column fluting, roof edges, sill projections. At 1-2 cm scale, even sub-millimeter geometry must read clearly.

### Lighting Rig

Use a three-point lighting setup plus ambient:

```javascript
initLighting() {
  // Ambient: soft fill so no face is pure black
  const ambient = new THREE.AmbientLight(0xffffff, 0.4);
  this.scene.add(ambient);

  // Hemisphere: subtle sky/ground color variation for natural feel
  const hemi = new THREE.HemisphereLight(0xc8d8e8, 0x886644, 0.3);
  this.scene.add(hemi);

  // Key light: main directional, casts shadows to reveal depth
  this.keyLight = new THREE.DirectionalLight(0xffffff, 1.2);
  this.keyLight.position.set(25, 40, 20);
  this.keyLight.castShadow = true;

  // Shadow map tuned for small models:
  // tight frustum = higher effective resolution
  this.keyLight.shadow.mapSize.width = 1024;
  this.keyLight.shadow.mapSize.height = 1024;
  this.keyLight.shadow.camera.near = 1;
  this.keyLight.shadow.camera.far = 100;
  this.keyLight.shadow.camera.left = -30;
  this.keyLight.shadow.camera.right = 30;
  this.keyLight.shadow.camera.top = 30;
  this.keyLight.shadow.camera.bottom = -30;
  this.keyLight.shadow.bias = -0.001;
  this.keyLight.shadow.normalBias = 0.02;
  this.scene.add(this.keyLight);

  // Fill light: softer, opposite side, no shadow
  const fillLight = new THREE.DirectionalLight(0xb0c4de, 0.5);
  fillLight.position.set(-20, 20, -10);
  this.scene.add(fillLight);

  // Rim light: from behind, highlights silhouette edges
  const rimLight = new THREE.DirectionalLight(0xffeedd, 0.3);
  rimLight.position.set(-5, 15, -25);
  this.scene.add(rimLight);
}
```

### Architectural Material

A single material that reads as clean matte plastic/resin, similar to the final 3D print. Use `MeshStandardMaterial` with tuned roughness:

```javascript
createArchitecturalMaterial() {
  return new THREE.MeshStandardMaterial({
    color: 0xd4c8b8,       // Warm neutral (looks like resin/sandstone)
    roughness: 0.65,        // Matte but not completely flat
    metalness: 0.0,         // Non-metallic
    flatShading: false,     // Smooth shading reveals surface curvature
    side: THREE.FrontSide,  // Only front faces (models are watertight)
  });
}
```

### Edge Highlighting with EdgesGeometry

For architectural models, edge lines dramatically improve readability. Apply them to every loaded mesh:

```javascript
addEdgeHighlighting(model) {
  const edgeLinesToAdd = [];

  model.traverse((child) => {
    if (child.isMesh) {
      const edges = new THREE.EdgesGeometry(child.geometry, 30);
      // 30-degree threshold: only show edges where face angle
      // exceeds 30 degrees, suppressing tessellation artifacts
      // while preserving architectural edges
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({
          color: 0x333333,
          linewidth: 1,       // Note: linewidth > 1 only works on some GPUs
          transparent: true,
          opacity: 0.35,
          depthTest: true,
        })
      );
      // Copy the mesh's world transform
      line.position.copy(child.position);
      line.rotation.copy(child.rotation);
      line.scale.copy(child.scale);
      edgeLinesToAdd.push({ parent: child.parent, line });
    }
  });

  // Add edge lines after traversal to avoid modifying the tree mid-walk
  for (const { parent, line } of edgeLinesToAdd) {
    parent.add(line);
  }
}
```

**Threshold angle of 30 degrees** is critical: the backend's CSG output is triangulated. Without a threshold, every triangle edge would render, producing visual noise. At 30 degrees, only meaningful architectural edges (wall corners, window frames, roof ridges) appear.

### Screen-Space Ambient Occlusion (Optional Enhancement)

For higher-end machines, SSAO via post-processing adds contact shadows in window recesses and under overhangs. This is the highest-impact enhancement for architectural visualization but comes at a performance cost:

```javascript
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

initPostProcessing() {
  this.composer = new EffectComposer(this.renderer);

  const renderPass = new RenderPass(this.scene, this.camera);
  this.composer.addPass(renderPass);

  this.ssaoPass = new SSAOPass(
    this.scene,
    this.camera,
    this.container.clientWidth,
    this.container.clientHeight
  );
  this.ssaoPass.kernelRadius = 4;    // Tuned for small models
  this.ssaoPass.minDistance = 0.001;
  this.ssaoPass.maxDistance = 0.15;
  this.ssaoPass.intensity = 1.5;     // Strong enough to read at small scale
  this.composer.addPass(this.ssaoPass);

  const outputPass = new OutputPass();
  this.composer.addPass(outputPass);
}

// In animate(), replace this.renderer.render() with:
animate() {
  requestAnimationFrame(() => this.animate());
  this.controls.update();
  if (this.composer) {
    this.composer.render();
  } else {
    this.renderer.render(this.scene, this.camera);
  }
}
```

Make SSAO optional with a toggle in the UI. Detect performance via `renderer.info.render.frame` timing and disable automatically if frame rate drops below 30 fps.

---

## 7. Download STL Button Integration

The STL download calls a separate backend endpoint (`POST /export/stl`) with the same parameters used for preview generation. This avoids regenerating the model on the client side.

```javascript
async function downloadSTL(style, params) {
  const btn = document.getElementById('btn-download-stl');
  btn.disabled = true;
  btn.textContent = 'Generating STL...';

  try {
    const response = await fetch('/export/stl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style, ...params }),
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || `Export failed: ${response.status}`);
    }

    // Extract filename from Content-Disposition header if available
    const disposition = response.headers.get('Content-Disposition');
    let filename = `hotel-${style}.stl`;
    if (disposition) {
      const match = disposition.match(/filename="?([^";\n]+)"?/);
      if (match) filename = match[1];
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    // Trigger download via ephemeral anchor element
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();

    // Cleanup
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);
  } catch (err) {
    showErrorToast(`STL download failed: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Download STL';
  }
}
```

### Wire to Button

```javascript
document.getElementById('btn-download-stl').addEventListener('click', () => {
  const style = document.getElementById('style-select').value;
  const params = paramUI.getParams();
  downloadSTL(style, params);
});
```

### Backend Endpoint Reference

The corresponding FastAPI endpoint should set appropriate headers:

```python
from fastapi.responses import Response

@app.post("/export/stl")
async def export_stl(params: BuildingParams):
    mesh = generate_building(params)
    stl_bytes = export_as_stl(mesh)
    filename = f"hotel-{params.style}-{params.width}x{params.depth}.stl"
    return Response(
        content=stl_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
```

---

## 8. Performance Considerations

### Model Size Budget

At game-piece scale (1-2 cm), typical triangle counts are modest:

| Complexity | Triangle Count | GLB Size | Load Time |
|---|---|---|---|
| Simple (Modern) | 500-2,000 | 10-40 KB | < 50 ms |
| Medium (Art Deco) | 2,000-8,000 | 40-150 KB | < 100 ms |
| Complex (Victorian) | 8,000-20,000 | 150-400 KB | < 200 ms |

These are small by three.js standards. The bottleneck is the backend generation time (CSG booleans), not the frontend rendering.

### Backend Generation Time Targets

- Target: < 500ms for simple styles, < 2s for complex styles.
- The 300ms debounce plus network latency means the user sees results within roughly 500ms-2.5s of releasing a slider.
- If generation exceeds 3s, consider showing a progress indicator or generating at reduced fidelity first.

### Request Deduplication

Avoid sending identical requests. Cache the last request parameters and skip if unchanged:

```javascript
let lastRequestHash = '';

function paramsHash(style, params) {
  return JSON.stringify({ style, ...params });
}

async function requestPreview(style, params, preview) {
  const hash = paramsHash(style, params);
  if (hash === lastRequestHash) return;
  lastRequestHash = hash;
  // ... proceed with fetch
}
```

### GPU Memory Management

Three.js does not garbage-collect GPU resources. Every model replacement must explicitly dispose geometries and materials (as shown in `disposeObject` above). Additionally, track total allocated memory:

```javascript
logMemoryStats() {
  const info = this.renderer.info;
  console.log(
    `Geometries: ${info.memory.geometries}, ` +
    `Textures: ${info.memory.textures}, ` +
    `Draw calls: ${info.render.calls}`
  );
}
```

Call this after each model load during development. If geometry count climbs over time, there is a disposal leak.

### Error Handling Strategy

Errors fall into three categories:

**Network errors** (fetch failures, timeouts):
```javascript
showErrorToast(message, duration = 5000) {
  const toast = document.getElementById('error-toast');
  toast.textContent = message;
  toast.classList.remove('hidden');
  clearTimeout(this.errorTimer);
  this.errorTimer = setTimeout(() => {
    toast.classList.add('hidden');
  }, duration);
}
```

**Backend validation errors** (invalid parameter combinations):
The backend returns 422 with a Pydantic validation error body. Parse and display the specific field error:
```javascript
if (response.status === 422) {
  const body = await response.json();
  const details = body.detail
    .map(d => `${d.loc.join('.')}: ${d.msg}`)
    .join('; ');
  throw new Error(`Invalid parameters: ${details}`);
}
```

**GLB parse errors** (corrupted response):
Wrap `GLTFLoader.parse` in try/catch and show a generic "Model load failed" message. Retain the previous model in the viewport so the user is not left with a blank screen.

### Pixel Ratio Capping

High-DPI screens (Retina, 4K) can quadruple fill rate cost for no perceptible benefit on a 3D viewport. Cap at 2x:

```javascript
this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
```

### Lazy Initialization of Post-Processing

Only initialize SSAO and other post-processing effects if the user opts in (via a "High Quality" toggle) or if the device demonstrates sufficient performance during the first few frames:

```javascript
initAdaptiveQuality() {
  let frameTimes = [];

  const measure = () => {
    const start = performance.now();
    this.renderer.render(this.scene, this.camera);
    frameTimes.push(performance.now() - start);

    if (frameTimes.length >= 30) {
      const avg = frameTimes.reduce((a, b) => a + b) / frameTimes.length;
      if (avg < 10) {
        // Rendering under 10ms per frame: enable post-processing
        this.initPostProcessing();
      }
      // Stop measuring
      return;
    }
    requestAnimationFrame(measure);
  };
  requestAnimationFrame(measure);
}
```

---

## Appendix A: Complete Application Bootstrap

Tying everything together in `app.js`:

```javascript
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// (HotelPreview class as defined above)
// (ParameterUI class as defined above)
// (requestPreview, downloadSTL functions as defined above)

async function main() {
  const container = document.getElementById('viewport-container');
  const preview = new HotelPreview(container);

  const paramContainer = document.getElementById('params-container');
  const styleSelect = document.getElementById('style-select');

  let currentStyle = '';

  const debouncedPreview = debounce((style, params) => {
    requestPreview(style, params, preview);
  }, 300);

  const paramUI = new ParameterUI(paramContainer, (params) => {
    debouncedPreview(currentStyle, params);
  });

  // Load styles from backend and wire up selector
  try {
    const resp = await fetch('/styles');
    const data = await resp.json();
    const styles = data.styles;
    const styleMap = {};

    for (const style of styles) {
      const opt = document.createElement('option');
      opt.value = style.name;
      opt.textContent = style.display_name;
      styleSelect.appendChild(opt);
      styleMap[style.name] = style;
    }

    styleSelect.addEventListener('change', () => {
      currentStyle = styleSelect.value;
      const style = styleMap[currentStyle];
      if (style) {
        paramUI.buildFromSchema(style.params_schema);
        requestPreview(currentStyle, paramUI.getParams(), preview);
      }
    });

    // Initialize with first style
    if (styles.length > 0) {
      styleSelect.value = styles[0].name;
      styleSelect.dispatchEvent(new Event('change'));
    }
  } catch (err) {
    preview.showError('Failed to load styles from server');
  }

  // Download button
  document.getElementById('btn-download-stl').addEventListener('click', () => {
    downloadSTL(currentStyle, paramUI.getParams());
  });

  // Reset view button
  document.getElementById('btn-reset-view').addEventListener('click', () => {
    preview.resetView();
  });
}

main();
```

## Appendix B: FastAPI Static File Serving

The backend should serve the `web/` directory as static files and mount the API:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# API routes registered first (they take priority)
# app.post("/generate")(generate_handler)
# app.post("/export/stl")(export_stl_handler)
# app.get("/styles")(styles_handler)

# Static files last (fallback)
app.mount("/", StaticFiles(directory="web", html=True), name="web")
```

Setting `html=True` enables serving `index.html` for the root path.

## Appendix C: Key three.js API Reference

| API | Purpose in This Project |
|---|---|
| `THREE.WebGLRenderer` | Canvas rendering with shadow maps and tone mapping |
| `THREE.PerspectiveCamera` | Perspective view suitable for small 3D objects |
| `THREE.Scene` | Container for models, lights, and helpers |
| `THREE.MeshStandardMaterial` | PBR material for realistic matte/plastic appearance |
| `THREE.EdgesGeometry` | Extract visible edges for architectural line drawing |
| `THREE.LineSegments` | Render edge lines |
| `THREE.DirectionalLight` | Key/fill/rim lighting with shadow casting |
| `THREE.AmbientLight` | Base fill to prevent pure-black faces |
| `THREE.HemisphereLight` | Sky/ground color variation |
| `THREE.Box3` | Bounding box computation for auto-framing |
| `GLTFLoader.parse()` | Load GLB from ArrayBuffer (not URL) |
| `OrbitControls` | Mouse/touch camera orbit, zoom, and pan |
| `EffectComposer` | Post-processing pipeline (optional SSAO) |
| `SSAOPass` | Screen-space ambient occlusion |
| `ResizeObserver` | Responsive viewport resize (browser API, not three.js) |

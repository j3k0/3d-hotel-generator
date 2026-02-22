import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

/**
 * HotelPreview — Three.js 3D preview of generated hotel models.
 */
class HotelPreview {
    constructor(container) {
        this.container = container;
        this.currentModel = null;
        this.loader = new GLTFLoader();

        this.initScene();
        this.initLighting();
        this.initControls();
        this.initResizeObserver();
        this.animate();
    }

    initScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1d23);

        // Camera
        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 200);
        this.camera.position.set(20, 15, 20);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.container.appendChild(this.renderer.domElement);

        // Ground plane
        const groundGeo = new THREE.PlaneGeometry(60, 60);
        const groundMat = new THREE.MeshStandardMaterial({
            color: 0x2a2d33,
            roughness: 0.9,
        });
        this.ground = new THREE.Mesh(groundGeo, groundMat);
        this.ground.rotation.x = -Math.PI / 2;
        this.ground.receiveShadow = true;
        this.scene.add(this.ground);

        // Grid helper
        this.gridHelper = new THREE.GridHelper(40, 40, 0x444444, 0x333333);
        this.gridHelper.position.y = 0.01;
        this.scene.add(this.gridHelper);

        // Material for hotel models
        this.hotelMaterial = new THREE.MeshStandardMaterial({
            color: 0xd4c5a9,
            roughness: 0.65,
            metalness: 0.0,
        });
    }

    initLighting() {
        // Ambient
        const ambient = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambient);

        // Hemisphere (soft fill from sky/ground)
        const hemi = new THREE.HemisphereLight(0xb0c4de, 0x3d3d3d, 0.4);
        this.scene.add(hemi);

        // Key light (directional + shadows)
        const key = new THREE.DirectionalLight(0xffffff, 1.2);
        key.position.set(15, 20, 10);
        key.castShadow = true;
        key.shadow.mapSize.width = 1024;
        key.shadow.mapSize.height = 1024;
        key.shadow.camera.near = 1;
        key.shadow.camera.far = 60;
        key.shadow.camera.left = -15;
        key.shadow.camera.right = 15;
        key.shadow.camera.top = 15;
        key.shadow.camera.bottom = -15;
        this.scene.add(key);

        // Fill light (opposite side)
        const fill = new THREE.DirectionalLight(0x8899aa, 0.5);
        fill.position.set(-10, 10, -5);
        this.scene.add(fill);

        // Rim light (behind)
        const rim = new THREE.DirectionalLight(0x667788, 0.3);
        rim.position.set(0, 5, -15);
        this.scene.add(rim);
    }

    initControls() {
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.target.set(0, 5, 0);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.08;
        this.controls.minDistance = 10;
        this.controls.maxDistance = 300;
        this.controls.minPolarAngle = 0.1;
        this.controls.maxPolarAngle = Math.PI / 2 - 0.05;
        this.controls.update();
    }

    initResizeObserver() {
        this.resizeObserver = new ResizeObserver(() => {
            const w = this.container.clientWidth;
            const h = this.container.clientHeight;
            if (w === 0 || h === 0) return;
            this.camera.aspect = w / h;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(w, h);
        });
        this.resizeObserver.observe(this.container);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    disposeObject(obj) {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
            if (Array.isArray(obj.material)) {
                obj.material.forEach(m => m.dispose());
            } else {
                obj.material.dispose();
            }
        }
        if (obj.children) {
            obj.children.forEach(child => this.disposeObject(child));
        }
    }

    loadGLB(arrayBuffer) {
        return new Promise((resolve, reject) => {
            this.loader.parse(arrayBuffer, '', (gltf) => {
                // Remove old model
                if (this.currentModel) {
                    this.disposeObject(this.currentModel);
                    this.scene.remove(this.currentModel);
                }

                const model = gltf.scene;

                // Apply hotel material to all meshes
                model.traverse((child) => {
                    if (child.isMesh) {
                        child.material = this.hotelMaterial;
                        child.castShadow = true;
                        child.receiveShadow = true;
                    }
                });

                // Add edge highlighting
                model.traverse((child) => {
                    if (child.isMesh) {
                        const edges = new THREE.EdgesGeometry(child.geometry, 30);
                        const line = new THREE.LineSegments(
                            edges,
                            new THREE.LineBasicMaterial({ color: 0x333333, linewidth: 1 })
                        );
                        child.add(line);
                    }
                });

                this.scene.add(model);
                this.currentModel = model;

                // Auto-frame the model
                this.frameModel(model);

                resolve(model);
            }, (error) => {
                reject(error);
            });
        });
    }

    frameModel(model) {
        const box = new THREE.Box3().setFromObject(model);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());

        // Set orbit target to model center
        this.controls.target.copy(center);

        // Position camera based on model size
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = this.camera.fov * (Math.PI / 180);
        const distance = maxDim / (2 * Math.tan(fov / 2)) * 2.5;

        this.camera.position.set(
            center.x + distance * 0.7,
            center.y + distance * 0.5,
            center.z + distance * 0.7
        );

        // Update near/far
        this.camera.near = distance * 0.01;
        this.camera.far = distance * 10;
        this.camera.updateProjectionMatrix();
        this.controls.update();

        // Resize ground plane and grid to fit model
        const groundSize = Math.max(size.x, size.z) * 2.5;
        this.ground.geometry.dispose();
        this.ground.geometry = new THREE.PlaneGeometry(groundSize, groundSize);

        if (this.gridHelper) this.scene.remove(this.gridHelper);
        const gridDivisions = Math.min(Math.round(groundSize / 2), 100);
        this.gridHelper = new THREE.GridHelper(groundSize * 0.8, gridDivisions, 0x444444, 0x333333);
        this.gridHelper.position.y = 0.01;
        this.scene.add(this.gridHelper);

        // Update shadow camera to cover model
        const shadowExtent = Math.max(size.x, size.z) * 0.8;
        const keyLight = this.scene.children.find(
            c => c.isDirectionalLight && c.castShadow
        );
        if (keyLight) {
            keyLight.shadow.camera.left = -shadowExtent;
            keyLight.shadow.camera.right = shadowExtent;
            keyLight.shadow.camera.top = shadowExtent;
            keyLight.shadow.camera.bottom = -shadowExtent;
            keyLight.shadow.camera.far = distance * 3;
            keyLight.shadow.camera.updateProjectionMatrix();
            // Reposition key light relative to model center
            keyLight.position.set(
                center.x + distance * 0.5,
                center.y + distance * 0.8,
                center.z + distance * 0.3
            );
            keyLight.target.position.copy(center);
            keyLight.target.updateMatrixWorld();
        }
    }

    resetView() {
        if (this.currentModel) {
            this.frameModel(this.currentModel);
        }
    }
}

/**
 * ParameterUI — Build controls from style JSON Schema.
 */
class ParameterUI {
    constructor(container, onChange) {
        this.container = container;
        this.onChange = onChange;
        this.params = {};
    }

    buildFromSchema(schema) {
        this.container.innerHTML = '';
        this.params = {};

        if (!schema || !schema.properties) return;

        for (const [key, prop] of Object.entries(schema.properties)) {
            const section = document.createElement('div');
            section.className = 'sidebar-section';

            const label = document.createElement('label');
            label.textContent = prop.description || key;
            section.appendChild(label);

            if (prop.type === 'boolean') {
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.checked = prop.default || false;
                this.params[key] = cb.checked;
                cb.addEventListener('change', () => {
                    this.params[key] = cb.checked;
                    this.onChange(this.params);
                });
                section.appendChild(cb);
            } else if (prop.type === 'string' && prop.enum) {
                const select = document.createElement('select');
                for (const opt of prop.enum) {
                    const option = document.createElement('option');
                    option.value = opt;
                    option.textContent = opt;
                    select.appendChild(option);
                }
                select.value = prop.default || prop.enum[0];
                this.params[key] = select.value;
                select.addEventListener('change', () => {
                    this.params[key] = select.value;
                    this.onChange(this.params);
                });
                section.appendChild(select);
            } else if (prop.type === 'number' || prop.type === 'integer') {
                const row = document.createElement('div');
                row.className = 'slider-row';
                const slider = document.createElement('input');
                slider.type = 'range';
                slider.min = prop.minimum || 0;
                slider.max = prop.maximum || 100;
                slider.step = prop.type === 'integer' ? 1 : 0.1;
                slider.value = prop.default || 0;
                const valueSpan = document.createElement('span');
                valueSpan.className = 'slider-value';
                valueSpan.textContent = slider.value;
                this.params[key] = Number(slider.value);
                slider.addEventListener('input', () => {
                    valueSpan.textContent = slider.value;
                    this.params[key] = Number(slider.value);
                    this.onChange(this.params);
                });
                row.appendChild(slider);
                row.appendChild(valueSpan);
                section.appendChild(row);
            }

            this.container.appendChild(section);
        }
    }
}

/**
 * App — Main application controller.
 */
class App {
    constructor() {
        this.viewport = document.getElementById('viewport');
        this.preview = new HotelPreview(this.viewport);
        this.styleSelect = document.getElementById('style-select');
        this.printerSelect = document.getElementById('printer-select');
        this.presetSelect = document.getElementById('preset-select');
        this.roadShapeSelect = document.getElementById('road-shape-select');
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.errorToast = document.getElementById('error-toast');
        this.buildInfo = document.getElementById('build-info');

        this.paramUI = new ParameterUI(
            document.getElementById('style-params-container'),
            () => this.debouncedGenerate()
        );

        this.abortController = null;
        this.debounceTimer = null;
        this.generationCounter = 0;
        this.lastParamsHash = '';
        this.styles = [];
        this.presets = [];
        this.mode = 'single'; // 'single' | 'complex' | 'board'

        this.init();
    }

    async init() {
        // Load styles
        try {
            const res = await fetch('/styles');
            const data = await res.json();
            this.styles = data.styles;

            for (const style of this.styles) {
                const opt = document.createElement('option');
                opt.value = style.name;
                opt.textContent = style.display_name;
                this.styleSelect.appendChild(opt);
            }

            this.onStyleChange();
        } catch (e) {
            this.showError('Failed to load styles: ' + e.message);
        }

        // Load presets
        await this.loadPresets();

        // Mode tabs
        this.initModeTabs();

        // Event listeners
        this.styleSelect.addEventListener('change', () => this.onStyleChange());
        this.printerSelect.addEventListener('change', () => this.debouncedGenerate());
        this.presetSelect.addEventListener('change', () => this.onPresetChange());
        this.roadShapeSelect.addEventListener('change', () => this.debouncedGenerate());

        // Sliders
        for (const id of ['seed', 'width', 'depth', 'floors', 'floor-height', 'buildings', 'spacing']) {
            const slider = document.getElementById(`${id}-slider`);
            const value = document.getElementById(`${id}-value`);
            if (slider && value) {
                slider.addEventListener('input', () => {
                    value.textContent = slider.value;
                    this.debouncedGenerate();
                });
            }
        }

        // Buttons
        document.getElementById('btn-reset-view').addEventListener('click', () => {
            this.preview.resetView();
        });
        document.getElementById('btn-download').addEventListener('click', () => {
            this.downloadSTL();
        });
    }

    initModeTabs() {
        const tabs = document.querySelectorAll('.mode-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.mode = tab.dataset.mode;
                this.updateModeVisibility();
                this.lastParamsHash = ''; // force regenerate
                this.debouncedGenerate();
            });
        });
    }

    updateModeVisibility() {
        const complexEls = document.querySelectorAll('.complex-only');
        complexEls.forEach(el => {
            el.style.display = this.mode === 'complex' ? '' : 'none';
        });
        const boardEls = document.querySelectorAll('.board-only');
        boardEls.forEach(el => {
            el.style.display = this.mode === 'board' ? '' : 'none';
        });
        // Hide single/complex-specific controls in board mode
        const buildingControls = document.querySelectorAll(
            '#style-params-container, [for="style-select"]'
        );
        const singleComplexSections = [
            'style-select', 'width-slider', 'depth-slider',
            'floors-slider', 'floor-height-slider',
        ];
        for (const id of singleComplexSections) {
            const el = document.getElementById(id);
            if (el) {
                const section = el.closest('.sidebar-section');
                if (section && !section.classList.contains('board-only') &&
                    !section.classList.contains('complex-only')) {
                    section.style.display = this.mode === 'board' ? 'none' : '';
                }
            }
        }
        // Style params container
        const styleParamsContainer = document.getElementById('style-params-container');
        if (styleParamsContainer) {
            styleParamsContainer.style.display = this.mode === 'board' ? 'none' : '';
        }
    }

    async loadPresets() {
        try {
            const res = await fetch('/presets');
            const data = await res.json();
            this.presets = data.presets;

            for (const preset of this.presets) {
                const opt = document.createElement('option');
                opt.value = preset.name;
                opt.textContent = `${preset.display_name} (${preset.style_name}, ${preset.num_buildings} bldgs)`;
                this.presetSelect.appendChild(opt);
            }
        } catch (e) {
            // Presets are optional
        }
    }

    onPresetChange() {
        const presetName = this.presetSelect.value;
        if (!presetName) {
            this.debouncedGenerate();
            return;
        }

        const preset = this.presets.find(p => p.name === presetName);
        if (preset) {
            // Auto-fill style and building count from preset
            this.styleSelect.value = preset.style_name;
            this.onStyleChange();
            document.getElementById('buildings-slider').value = preset.num_buildings;
            document.getElementById('buildings-value').textContent = preset.num_buildings;
        }
        this.debouncedGenerate();
    }

    onStyleChange() {
        const style = this.styles.find(s => s.name === this.styleSelect.value);
        if (style) {
            this.paramUI.buildFromSchema(style.params_schema);
        }
        this.debouncedGenerate();
    }

    getParams() {
        return {
            style_name: this.styleSelect.value,
            printer_type: this.printerSelect.value,
            seed: Number(document.getElementById('seed-slider').value),
            width: Number(document.getElementById('width-slider').value),
            depth: Number(document.getElementById('depth-slider').value),
            num_floors: Number(document.getElementById('floors-slider').value),
            floor_height: Number(document.getElementById('floor-height-slider').value),
            style_params: { ...this.paramUI.params },
        };
    }

    getComplexParams() {
        const presetName = this.presetSelect.value || undefined;
        return {
            style_name: this.styleSelect.value,
            num_buildings: Number(document.getElementById('buildings-slider').value),
            printer_type: this.printerSelect.value,
            seed: Number(document.getElementById('seed-slider').value),
            building_spacing: Number(document.getElementById('spacing-slider').value),
            style_params: { ...this.paramUI.params },
            preset: presetName,
        };
    }

    getBoardParams() {
        return {
            road_shape: this.roadShapeSelect.value,
            printer_type: this.printerSelect.value,
            seed: Number(document.getElementById('seed-slider').value),
        };
    }

    debouncedGenerate() {
        clearTimeout(this.debounceTimer);
        const delay = this.mode === 'board' ? 1000 : 300;
        this.debounceTimer = setTimeout(() => this.generate(), delay);
    }

    async generate() {
        let params, endpoint, metadataHeader;
        if (this.mode === 'board') {
            params = this.getBoardParams();
            endpoint = '/board/preview';
            metadataHeader = 'X-Board-Metadata';
        } else if (this.mode === 'complex') {
            params = this.getComplexParams();
            endpoint = '/complex/generate';
            metadataHeader = 'X-Complex-Metadata';
        } else {
            params = this.getParams();
            endpoint = '/generate';
            metadataHeader = 'X-Build-Metadata';
        }

        const hash = JSON.stringify({ mode: this.mode, ...params });
        if (hash === this.lastParamsHash) return;
        this.lastParamsHash = hash;

        // Cancel previous request
        if (this.abortController) {
            this.abortController.abort();
        }
        this.abortController = new AbortController();

        const counter = ++this.generationCounter;

        this.showLoading(true);
        this.hideError();

        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params),
                signal: this.abortController.signal,
            });

            if (counter !== this.generationCounter) return; // stale

            if (!res.ok) {
                const err = await res.json().catch(() => ({ message: 'Generation failed' }));
                throw new Error(err.message || `HTTP ${res.status}`);
            }

            const buffer = await res.arrayBuffer();
            if (counter !== this.generationCounter) return; // stale

            await this.preview.loadGLB(buffer);

            // Update build info
            const metadata = res.headers.get(metadataHeader);
            if (metadata) {
                const info = JSON.parse(metadata);
                this.showBuildInfo(info, this.mode);
            }
        } catch (e) {
            if (e.name === 'AbortError') return;
            this.showError(e.message);
        } finally {
            if (counter === this.generationCounter) {
                this.showLoading(false);
            }
        }
    }

    async downloadSTL() {
        const btn = document.getElementById('btn-download');
        btn.disabled = true;
        btn.textContent = 'Exporting...';

        try {
            if (this.mode === 'board') {
                const params = this.getBoardParams();
                const res = await fetch('/board/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(params),
                });

                if (!res.ok) throw new Error('Board export failed');

                const data = await res.json();
                const fileCount = data.files.filter(f => f.endsWith('.stl')).length;
                this.showError(`Exported ${fileCount} STL files (${data.num_properties} properties + frame) to server directory`);
            } else if (this.mode === 'complex') {
                const params = this.getComplexParams();
                const res = await fetch('/complex/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(params),
                });

                if (!res.ok) throw new Error('Complex export failed');

                const data = await res.json();
                const fileCount = data.files.filter(f => f.endsWith('.stl')).length;
                this.showError(`Exported ${fileCount} STL files to server directory`);
            } else {
                const params = this.getParams();
                const res = await fetch('/export/stl', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(params),
                });

                if (!res.ok) throw new Error('STL export failed');

                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `hotel_${params.style_name}_${params.seed}.stl`;
                a.click();
                URL.revokeObjectURL(url);
            }
        } catch (e) {
            this.showError('Download failed: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Download STL';
        }
    }

    showLoading(show) {
        this.loadingOverlay.style.display = show ? 'flex' : 'none';
    }

    showError(msg) {
        this.errorToast.textContent = msg;
        this.errorToast.style.display = 'block';
        setTimeout(() => this.hideError(), 5000);
    }

    hideError() {
        this.errorToast.style.display = 'none';
    }

    showBuildInfo(info, mode = 'single') {
        this.buildInfo.style.display = 'block';
        const infoBuildings = document.getElementById('info-buildings');

        if (mode === 'board') {
            document.getElementById('info-triangles').textContent =
                `Properties: ${info.num_properties} | Frame: ${info.num_frame_pieces || 0} pcs`;
            document.getElementById('info-size').textContent =
                `Layout: ${info.road_shape} | ${(info.generation_time_ms / 1000).toFixed(1)}s`;
            infoBuildings.style.display = '';
            const presetNames = (info.property_slots || []).map(s => s.preset).join(', ');
            infoBuildings.textContent = presetNames || 'No presets';
        } else if (mode === 'complex') {
            const totalTris = info.buildings
                ? info.buildings.reduce((sum, b) => sum + b.triangle_count, 0)
                : 0;
            document.getElementById('info-triangles').textContent =
                `Triangles: ${totalTris.toLocaleString()}`;
            document.getElementById('info-size').textContent =
                `Lot: ${info.lot_width.toFixed(1)} x ${info.lot_depth.toFixed(1)} mm`;
            infoBuildings.style.display = '';
            infoBuildings.textContent = `Buildings: ${info.num_buildings}`;
        } else {
            document.getElementById('info-triangles').textContent =
                `Triangles: ${info.triangle_count.toLocaleString()}`;
            if (info.bounding_box) {
                const bb = info.bounding_box;
                const w = (bb[3] - bb[0]).toFixed(1);
                const d = (bb[4] - bb[1]).toFixed(1);
                const h = (bb[5] - bb[2]).toFixed(1);
                document.getElementById('info-size').textContent =
                    `Size: ${w} x ${d} x ${h} mm`;
            }
            infoBuildings.style.display = 'none';
        }
    }
}

// Start app
new App();

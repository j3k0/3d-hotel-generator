#!/bin/bash
# Setup script for Claude Code cloud environment.
# Installs Python dependencies and system libraries for headless rendering.
#
# Usage:
#   bash scripts/setup_environment.sh
#
# This script handles the cloud environment's DNS limitation by downloading
# system .deb packages directly via Python urllib instead of apt-get.
set -e

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

echo "=== Setting up 3D Hotel Generator environment ==="

# 1. Install core Python dependencies
echo ""
echo "--- Installing Python dependencies ---"
if [ -f pyproject.toml ]; then
    pip install -e ".[dev]" 2>&1 | tail -5
else
    echo "No pyproject.toml yet (expected before Step 1). Installing core deps directly..."
    pip install "manifold3d>=3.3.2,<4.0" "trimesh>=4.0,<5.0" "numpy>=1.24" \
        "fastapi>=0.100,<1.0" "uvicorn>=0.20" "pydantic>=2.0,<3.0" \
        "pydantic-settings>=2.0" "pytest>=7.0" "httpx>=0.24" 2>&1 | tail -5
fi

# 2. Install headless rendering dependencies (OSMesa + pyrender)
echo ""
echo "--- Installing headless rendering dependencies ---"

# Install system-level OSMesa and GLU via direct .deb download
# (apt-get DNS resolution may not work in cloud environments)
python3 << 'PYTHON_SCRIPT'
import subprocess
import os
import sys

DEBS = {
    "libosmesa6": "http://archive.ubuntu.com/ubuntu/pool/main/m/mesa-compat/libosmesa6_25.1.7-1ubuntu2~24.04.1_amd64.deb",
    "libopengl0": "http://archive.ubuntu.com/ubuntu/pool/main/libg/libglvnd/libopengl0_1.7.0-1build1_amd64.deb",
    "libglu1-mesa": "http://archive.ubuntu.com/ubuntu/pool/main/libg/libglu/libglu1-mesa_9.0.2-1.1build1_amd64.deb",
}

for name, url in DEBS.items():
    deb_path = f"/tmp/{name}.deb"

    # Check if already installed
    check = subprocess.run(["dpkg", "-s", name], capture_output=True)
    if check.returncode == 0:
        print(f"  {name}: already installed")
        continue

    # Download
    if not os.path.exists(deb_path):
        print(f"  {name}: downloading...")
        try:
            import urllib.request
            urllib.request.urlretrieve(url, deb_path)
        except Exception as e:
            print(f"  {name}: download failed ({e}), skipping")
            continue

    # Install
    print(f"  {name}: installing...")
    result = subprocess.run(["dpkg", "-i", deb_path], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  {name}: install failed: {result.stderr.strip()}")
    else:
        print(f"  {name}: installed successfully")
PYTHON_SCRIPT

# Install pyrender with workaround for PyOpenGL version conflict
echo ""
echo "--- Installing pyrender ---"
pip install "PyOpenGL>=3.1.0" 2>&1 | tail -2
pip install pyrender --no-deps 2>&1 | tail -2
pip install Pillow 2>&1 | tail -2

# 3. Set environment variable for headless rendering
export PYOPENGL_PLATFORM=osmesa

# 4. Verify rendering works
echo ""
echo "--- Verifying headless rendering ---"
python3 -c "
import os
os.environ['PYOPENGL_PLATFORM'] = 'osmesa'
try:
    import pyrender
    import trimesh
    import numpy as np
    # Create a simple box and try to render it
    mesh = trimesh.creation.box(extents=[1, 1, 1])
    scene = pyrender.Scene()
    scene.add(pyrender.Mesh.from_trimesh(mesh))
    camera = pyrender.PerspectiveCamera(yfov=0.6)
    import numpy as np
    pose = np.eye(4)
    pose[2, 3] = 3
    scene.add(camera, pose=pose)
    light = pyrender.DirectionalLight(intensity=3.0)
    scene.add(light, pose=pose)
    r = pyrender.OffscreenRenderer(320, 240)
    color, depth = r.render(scene)
    r.delete()
    print(f'  Headless rendering: OK (rendered {color.shape[1]}x{color.shape[0]} image)')
except ImportError as e:
    print(f'  Headless rendering: UNAVAILABLE ({e})')
    print('  (Rendering scripts will not work, but core generation is unaffected)')
except Exception as e:
    print(f'  Headless rendering: FAILED ({e})')
    print('  (Rendering scripts will not work, but core generation is unaffected)')
"

# 5. Verify anthropic SDK
echo ""
echo "--- Checking Anthropic API ---"
pip install anthropic 2>&1 | tail -2
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "  ANTHROPIC_API_KEY: set"
else
    echo "  ANTHROPIC_API_KEY: NOT SET (critique loop will be skipped)"
fi

echo ""
echo "=== Environment setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Read CLAUDE.md for development instructions"
echo "  2. Read plan.md for implementation steps"
echo "  3. Start with Step 1: python scripts/validate_step.py --step 1"

#!/usr/bin/env python3
"""
Headless rendering of a hotel GLB to PNG images.

Renders a generated hotel from multiple angles for visual inspection
and vision model critique. Requires pyrender + OSMesa for headless operation.

Usage:
    PYOPENGL_PLATFORM=osmesa python scripts/render_hotel.py --style modern --seed 42
    PYOPENGL_PLATFORM=osmesa python scripts/render_hotel.py --style victorian --output renders/
    PYOPENGL_PLATFORM=osmesa python scripts/render_hotel.py --style modern --supersample 1

Environment:
    PYOPENGL_PLATFORM=osmesa  (required for headless rendering)

Install:
    sudo apt-get install -y libosmesa6-dev
    pip install ".[render]"
"""
import argparse
import io
import os
import sys
from pathlib import Path

# Must be set before any OpenGL import
if "PYOPENGL_PLATFORM" not in os.environ:
    os.environ["PYOPENGL_PLATFORM"] = "osmesa"

import numpy as np

# Monkey-patch for pyrender compatibility with NumPy 2.0+
# pyrender uses np.infty which was removed in NumPy 2.0
if not hasattr(np, "infty"):
    np.infty = np.inf


# Default camera angles: (azimuth_deg, elevation_deg, label)
DEFAULT_ANGLES = [
    (45, 30, "front_3q"),    # 3/4 front view (hero shot)
    (135, 30, "back_3q"),    # 3/4 back view
    (0, 0, "front"),         # front elevation
    (0, 80, "top"),          # near top-down
]


def _make_directional_light_pose(direction):
    """Build a 4x4 pose matrix for a directional light pointing along `direction`."""
    d = np.array(direction, dtype=float)
    d = d / np.linalg.norm(d)
    pose = np.eye(4)
    pose[:3, 2] = -d
    return pose


def _build_ground_plane(bounds, size):
    """Create a ground-plane trimesh at the model's base z-coordinate."""
    import trimesh

    ground_z = float(bounds[0][2])
    half = size * 1.5
    cx = float((bounds[0][0] + bounds[1][0]) / 2)
    cy = float((bounds[0][1] + bounds[1][1]) / 2)
    vertices = np.array([
        [cx - half, cy - half, ground_z],
        [cx + half, cy - half, ground_z],
        [cx + half, cy + half, ground_z],
        [cx - half, cy + half, ground_z],
    ], dtype=np.float64)
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _post_process(img):
    """Apply subtle post-processing to improve render quality."""
    from PIL import ImageEnhance

    # Boost contrast to deepen shadows without clipping highlights
    img = ImageEnhance.Contrast(img).enhance(1.10)
    return img


def _render_single_angle(
    tri_mesh,
    center: np.ndarray,
    size: float,
    bounds: np.ndarray,
    angle: tuple[float, float, str],
    resolution: tuple[int, int],
    supersample: int = 2,
) -> "Image.Image":
    """
    Render a trimesh from a single camera angle.

    Returns a PIL Image at the requested resolution.
    """
    import pyrender
    from PIL import Image

    azimuth_deg, elevation_deg, _label = angle

    # Internal resolution for supersampling
    render_w = resolution[0] * supersample
    render_h = resolution[1] * supersample

    # Build pyrender scene
    scene = pyrender.Scene(
        bg_color=[0.62, 0.65, 0.70, 1.0],
        ambient_light=[0.12, 0.12, 0.12],
    )

    # Material: warm matte plastic (like a 3D print)
    material = pyrender.MetallicRoughnessMaterial(
        baseColorFactor=[0.72, 0.68, 0.63, 1.0],
        metallicFactor=0.0,
        roughnessFactor=0.7,
    )
    render_mesh = pyrender.Mesh.from_trimesh(tri_mesh, material=material)
    scene.add(render_mesh)

    # Ground plane with shadow (skip for top-down views)
    add_ground = elevation_deg < 70
    if add_ground:
        ground_material = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.52, 0.54, 0.58, 1.0],
            metallicFactor=0.0,
            roughnessFactor=0.95,
        )
        ground_mesh = _build_ground_plane(bounds, size)
        ground_render = pyrender.Mesh.from_trimesh(ground_mesh, material=ground_material)
        scene.add(ground_render)

    # Camera position from spherical coordinates
    distance = size * 2.5
    az = np.radians(azimuth_deg)
    el = np.radians(elevation_deg)
    cam_x = center[0] + distance * np.cos(el) * np.sin(az)
    cam_y = center[1] + distance * np.cos(el) * np.cos(az)
    cam_z = center[2] + distance * np.sin(el)

    camera = pyrender.PerspectiveCamera(yfov=np.radians(35))

    # Build camera pose (look-at)
    cam_pos = np.array([cam_x, cam_y, cam_z])
    forward = center - cam_pos
    forward = forward / np.linalg.norm(forward)
    right = np.cross(forward, [0, 0, 1])
    if np.linalg.norm(right) < 1e-6:
        right = np.cross(forward, [0, 1, 0])
    right = right / np.linalg.norm(right)
    up = np.cross(right, forward)

    camera_pose = np.eye(4)
    camera_pose[:3, 0] = right
    camera_pose[:3, 1] = up
    camera_pose[:3, 2] = -forward
    camera_pose[:3, 3] = cam_pos
    scene.add(camera, pose=camera_pose)

    # Key light (from above-right, warm) — primary form-defining light
    key_light = pyrender.DirectionalLight(color=[1.0, 0.95, 0.9], intensity=2.2)
    scene.add(key_light, pose=_make_directional_light_pose([0.5, 0.3, -0.8]))

    # Fill light (from left, cool) — opens shadows without flattening
    fill_light = pyrender.DirectionalLight(color=[0.65, 0.70, 0.80], intensity=0.7)
    scene.add(fill_light, pose=_make_directional_light_pose([-0.5, -0.3, -0.5]))

    # Rim light (from behind-above) — edge separation from background
    rim_light = pyrender.DirectionalLight(color=[0.90, 0.85, 0.80], intensity=1.0)
    scene.add(rim_light, pose=_make_directional_light_pose([0.0, -0.5, -0.8]))

    # Render at supersampled resolution
    renderer = pyrender.OffscreenRenderer(render_w, render_h)
    flags = pyrender.RenderFlags.SHADOWS_DIRECTIONAL if add_ground else pyrender.RenderFlags.NONE
    color, _ = renderer.render(scene, flags=flags)
    renderer.delete()

    # Convert to PIL and downsample
    img = Image.fromarray(color)
    if supersample > 1:
        img = img.resize(resolution, Image.LANCZOS)

    # Post-processing
    img = _post_process(img)

    return img


def render_manifold_to_images(
    manifold,
    output_dir: str,
    style_name: str,
    resolution: tuple[int, int] = (1024, 1024),
    angles: list[tuple[float, float, str]] | None = None,
    supersample: int = 2,
) -> list[str]:
    """
    Render a Manifold from multiple camera angles to PNG files.

    Returns list of output file paths.
    """
    try:
        import trimesh
    except ImportError:
        print("ERROR: Rendering requires pyrender, PyOpenGL, trimesh, and Pillow.")
        print("Install with: pip install pyrender PyOpenGL Pillow")
        print("Also: sudo apt-get install -y libosmesa6-dev")
        sys.exit(1)

    if angles is None:
        angles = DEFAULT_ANGLES

    # Convert manifold to trimesh
    mesh_data = manifold.to_mesh()
    tri_mesh = trimesh.Trimesh(
        vertices=mesh_data.vert_properties[:, :3],
        faces=mesh_data.tri_verts,
    )

    # Compute model center and size for camera positioning
    bounds = tri_mesh.bounds
    center = (bounds[0] + bounds[1]) / 2
    size = np.linalg.norm(bounds[1] - bounds[0])

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    paths = []

    for angle in angles:
        img = _render_single_angle(
            tri_mesh, center, size, bounds, angle, resolution, supersample,
        )

        filename = f"{style_name}_{angle[2]}.png"
        filepath = output_path / filename
        img.save(filepath)
        paths.append(str(filepath))
        print(f"  Rendered: {filepath}")

    return paths


def render_manifold_to_png_bytes(
    manifold,
    resolution: tuple[int, int] = (512, 512),
    angle: tuple[float, float, str] = (45, 30, "front_3q"),
    supersample: int = 2,
) -> bytes:
    """
    Render a Manifold from a single angle and return PNG bytes.

    Useful for API endpoints that need to serve PNG images directly.
    """
    import trimesh

    mesh_data = manifold.to_mesh()
    tri_mesh = trimesh.Trimesh(
        vertices=mesh_data.vert_properties[:, :3],
        faces=mesh_data.tri_verts,
    )

    bounds = tri_mesh.bounds
    center = (bounds[0] + bounds[1]) / 2
    size = np.linalg.norm(bounds[1] - bounds[0])

    img = _render_single_angle(
        tri_mesh, center, size, bounds, angle, resolution, supersample,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_and_render(
    style_name: str,
    seed: int = 42,
    printer_type: str = "fdm",
    output_dir: str = "renders",
    resolution: tuple[int, int] = (1024, 1024),
    supersample: int = 2,
) -> list[str]:
    """Full pipeline: generate hotel, then render from multiple angles."""
    from hotel_generator.assembly.building import HotelBuilder
    from hotel_generator.config import BuildingParams
    from hotel_generator.settings import Settings

    print(f"Generating {style_name} hotel (seed={seed}, printer={printer_type})...")
    params = BuildingParams(
        style_name=style_name,
        width=8.0,
        depth=6.0,
        num_floors=4,
        floor_height=0.8,
        printer_type=printer_type,
        seed=seed,
    )
    builder = HotelBuilder(Settings())
    result = builder.build(params)

    print(f"  Triangles: {result.triangle_count}")
    print(f"  Watertight: {result.is_watertight}")
    print(f"  Volume: {result.manifold.volume():.2f} mm^3")

    print(f"Rendering {style_name}...")
    paths = render_manifold_to_images(
        result.manifold,
        output_dir=output_dir,
        style_name=style_name,
        resolution=resolution,
        supersample=supersample,
    )
    return paths


def main():
    parser = argparse.ArgumentParser(description="Render a hotel style to PNG images")
    parser.add_argument("--style", required=True, help="Style name (e.g., modern, victorian)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--printer", default="fdm", choices=["fdm", "resin"])
    parser.add_argument("--output", default="renders", help="Output directory")
    parser.add_argument("--resolution", type=int, default=1024, help="Image resolution (square)")
    parser.add_argument("--supersample", type=int, default=2, choices=[1, 2, 4],
                        help="Supersample factor for anti-aliasing (default: 2)")
    args = parser.parse_args()

    paths = generate_and_render(
        style_name=args.style,
        seed=args.seed,
        printer_type=args.printer,
        output_dir=args.output,
        resolution=(args.resolution, args.resolution),
        supersample=args.supersample,
    )
    print(f"\nGenerated {len(paths)} renders in {args.output}/")


if __name__ == "__main__":
    main()

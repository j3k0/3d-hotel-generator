#!/usr/bin/env python3
"""
Headless rendering of a hotel GLB to PNG images.

Renders a generated hotel from multiple angles for visual inspection
and vision model critique. Requires pyrender + OSMesa for headless operation.

Usage:
    PYOPENGL_PLATFORM=osmesa python scripts/render_hotel.py --style modern --seed 42
    PYOPENGL_PLATFORM=osmesa python scripts/render_hotel.py --style victorian --output renders/

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


# Default camera angles: (azimuth_deg, elevation_deg, label)
DEFAULT_ANGLES = [
    (45, 30, "front_3q"),    # 3/4 front view (hero shot)
    (135, 30, "back_3q"),    # 3/4 back view
    (0, 0, "front"),         # front elevation
    (0, 80, "top"),          # near top-down
]


def render_manifold_to_images(
    manifold,
    output_dir: str,
    style_name: str,
    resolution: tuple[int, int] = (1024, 1024),
    angles: list[tuple[float, float, str]] | None = None,
) -> list[str]:
    """
    Render a Manifold from multiple camera angles to PNG files.

    Returns list of output file paths.
    """
    try:
        import pyrender
        import trimesh
        from PIL import Image
    except ImportError:
        print("ERROR: Rendering requires pyrender, PyOpenGL, and Pillow.")
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

    for azimuth_deg, elevation_deg, label in angles:
        # Build pyrender scene
        scene = pyrender.Scene(
            bg_color=[0.82, 0.85, 0.88, 1.0],
            ambient_light=[0.3, 0.3, 0.3],
        )

        # Material: warm matte plastic (like a 3D print)
        material = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.83, 0.80, 0.75, 1.0],
            metallicFactor=0.0,
            roughnessFactor=0.65,
        )
        render_mesh = pyrender.Mesh.from_trimesh(tri_mesh, material=material)
        scene.add(render_mesh)

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

        # Key light (from above-right)
        key_light = pyrender.DirectionalLight(color=[1.0, 0.98, 0.95], intensity=4.0)
        key_pose = np.eye(4)
        key_dir = np.array([0.5, 0.3, -0.8])
        key_dir = key_dir / np.linalg.norm(key_dir)
        key_pose[:3, 2] = -key_dir
        scene.add(key_light, pose=key_pose)

        # Fill light (from left)
        fill_light = pyrender.DirectionalLight(color=[0.7, 0.75, 0.85], intensity=1.5)
        fill_pose = np.eye(4)
        fill_dir = np.array([-0.5, -0.3, -0.5])
        fill_dir = fill_dir / np.linalg.norm(fill_dir)
        fill_pose[:3, 2] = -fill_dir
        scene.add(fill_light, pose=fill_pose)

        # Render
        renderer = pyrender.OffscreenRenderer(*resolution)
        color, _ = renderer.render(scene)
        renderer.delete()

        # Save
        img = Image.fromarray(color)
        filename = f"{style_name}_{label}.png"
        filepath = output_path / filename
        img.save(filepath)
        paths.append(str(filepath))
        print(f"  Rendered: {filepath}")

    return paths


def generate_and_render(
    style_name: str,
    seed: int = 42,
    printer_type: str = "fdm",
    output_dir: str = "renders",
    resolution: tuple[int, int] = (1024, 1024),
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
    )
    return paths


def main():
    parser = argparse.ArgumentParser(description="Render a hotel style to PNG images")
    parser.add_argument("--style", required=True, help="Style name (e.g., modern, victorian)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--printer", default="fdm", choices=["fdm", "resin"])
    parser.add_argument("--output", default="renders", help="Output directory")
    parser.add_argument("--resolution", type=int, default=1024, help="Image resolution (square)")
    args = parser.parse_args()

    paths = generate_and_render(
        style_name=args.style,
        seed=args.seed,
        printer_type=args.printer,
        output_dir=args.output,
        resolution=(args.resolution, args.resolution),
    )
    print(f"\nGenerated {len(paths)} renders in {args.output}/")


if __name__ == "__main__":
    main()
